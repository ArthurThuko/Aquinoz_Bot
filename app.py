import threading
import logging
import random
import requests
import os
from flask import Flask, request, jsonify
from sqlalchemy import text as sqlalchemy_text

# Importações dos seus modelos e banco
from models import SessionLocal, User, Materia, Conteudo, Sessao, engine

# Importações dos seus serviços
from services.telegram import send_message, send_voice
from services.scraper import extrair_texto_da_url
from services.ai_assistant import pedir_ia
from services.chunker import chunk_text
from services.voice import gerar_audio_do_texto
from config import BASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuração de performance do SQLite (Modo WAL)
with engine.connect() as conn:
    conn.execute(sqlalchemy_text("PRAGMA journal_mode=WAL;"))

# --- BACKGROUND ---
def task_processor(chat_id, user_id, sessao_id, action_type, payload=None):
    db = SessionLocal()
    try:
        sessao = db.query(Sessao).get(sessao_id)

        if not sessao or not sessao.materia_ativa:
            send_message(chat_id, "⚠️ Nenhuma matéria ativa. Por favor, selecione uma no menu.")
            return

        # ==========================================
        # 1. GERAR RESUMO (COM BOTÃO DE VOZ)
        # ==========================================
        if action_type == "/resumir":
            materiais = db.query(Conteudo)\
                          .filter_by(materia_id=sessao.materia_ativa)\
                          .order_by(Conteudo.id.desc())\
                          .limit(5).all()
            
            if materiais:
                send_message(chat_id, "🤖 Lendo os últimos materiais e gerando um resumo...")
                materiais.reverse() 
                texto_compilado = "\n\n---\n\n".join([c.texto for c in materiais])
                
                prompt = "Com base no texto fornecido, crie um resumo direto ao ponto em poucos tópicos curtos. Use linguagem simples."
                res = pedir_ia(prompt, texto_compilado)
                
                # Botão para ouvir apenas este resumo (Economiza processamento e não buga)
                keyboard = {
                    "inline_keyboard": [[
                        {"text": "🔊 Ouvir este resumo", "callback_data": "tts_agora"}
                    ]]
                }
                send_message(chat_id, res, keyboard)
            else:
                send_message(chat_id, "📭 A matéria está vazia.")

        # ==========================================
        # 2. GERAR VOZ SOB DEMANDA
        # ==========================================
        elif action_type == "tts_agora":
            # Aqui o payload é o texto do resumo gerado
            send_message(chat_id, "🎙️ <b>Gravando áudio do resumo...</b>")
            caminho_audio = gerar_audio_do_texto(payload, user_id)
            
            if caminho_audio:
                send_voice(chat_id, caminho_audio)
                if os.path.exists(caminho_audio):
                    os.remove(caminho_audio)
            else:
                send_message(chat_id, "❌ Erro ao gerar áudio.")

        elif action_type == "/ouvir":
            # O /ouvir do menu lê os últimos conteúdos (Limitado a 2 para não bugar o Edge-TTS)
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).order_by(Conteudo.id.desc()).limit(2).all()
            if materiais:
                send_message(chat_id, "🤖 Gerando resumo...")
                texto = " ".join([c.texto for c in materiais])
                res = pedir_ia("Resuma em 5 tópicos curtos.", texto)
                send_message(chat_id, res)

        elif action_type == "/gerar_questoes":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            
            if materiais:
                send_message(chat_id, "🤖 Preparando seu teste...")
                amostra = random.sample(materiais, min(len(materiais), 4))
                texto_compilado = "\n\n---\n\n".join([c.texto for c in amostra])
                
                prompt = (
                    "Crie 3 questões de múltipla escolha (A, B, C, D). "
                    "Oculte APENAS a resposta final usando a tag <tg-spoiler>.\n\n"
                    "Exemplo: Gabarito: <tg-spoiler>Letra B - Explicação</tg-spoiler>"
                )
                
                res = pedir_ia(prompt, texto_compilado)
                
                keyboard_feedback = {
                    "inline_keyboard": [[
                        {"text": "✅ Acertei!", "callback_data": "feedback_bom"},
                        {"text": "❌ Errei", "callback_data": "feedback_ruim"}
                    ]]
                }
                send_message(chat_id, res, keyboard_feedback)
            else:
                send_message(chat_id, "📭 A matéria está vazia.")

        # ==========================================
        # 4. RESPONDER DÚVIDAS
        # ==========================================
        elif action_type == "/pergunta":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            if materiais:
                send_message(chat_id, "🔍 Vasculhando materiais...")
                texto_compilado = "\n\n---\n\n".join([c.texto for c in materiais[-5:]])
                prompt = f"O usuário perguntou: '{payload}'. Responda estritamente com base no texto ou diga que não sabe."
                res = pedir_ia(prompt, texto_compilado)
                send_message(chat_id, res)
            else:
                send_message(chat_id, "📭 A matéria está vazia.")

        # ==========================================
        # 5. AUTO SAVE
        # ==========================================
        elif action_type == "auto_save":
            if payload.startswith("http"):
                send_message(chat_id, "🌐 Extraindo texto do link...")
                texto_bruto = extrair_texto_da_url(payload)
                tipo = "link"
            else:
                texto_bruto = payload
                tipo = "texto"

            if texto_bruto:
                pedacos = chunk_text(texto_bruto, max_chars=1000, overlap=100)
                for pedaco in pedacos:
                    db.add(Conteudo(texto=pedaco, tipo=tipo, materia_id=sessao.materia_ativa))
                db.commit()
                send_message(chat_id, f"✅ Material salvo em {len(pedacos)} blocos!")

    except Exception as e:
        logger.error(f"Erro no processamento da task: {e}")
        send_message(chat_id, "❌ Erro ao processar solicitação.")
    finally:
        db.close()


# --- WEBHOOK ---
@app.route("/webhook", methods=["POST"])
def webhook():
    db = SessionLocal()
    try:
        data = request.json
        mensagem_original_texto = ""

        # Callback de Botões
        if "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["message"]["chat"]["id"]
            text = callback["data"]

            requests.post(f"{BASE_URL}/answerCallbackQuery", json={
                "callback_query_id": callback["id"]
            })

        else:
            msg = data.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text")

        if not chat_id or not text:
            return jsonify({"status": "ok"}), 200

        user = db.query(User).filter_by(telegram_id=str(chat_id)).one_or_none()
        if not user:
            user = User(telegram_id=str(chat_id))
            db.add(user); db.commit(); db.refresh(user)

        sessao = db.query(Sessao).filter_by(user_id=user.id).one_or_none()
        if not sessao:
            sessao = Sessao(user_id=user.id)
            db.add(sessao)
            db.commit()
            db.refresh(sessao)

        # --- MENU ---
        if text in ["/start", "/menu"]:
            keyboard = {
                "inline_keyboard": [
                    [{"text": "📚 Matérias", "callback_data": "listar_materias"}, {"text": "➕ Nova", "callback_data": "nova_materia"}],
                    [{"text": "📊 Resumir", "callback_data": "/resumir"}, {"text": "📝 Questões", "callback_data": "/gerar_questoes"}],
                    [{"text": "🎙️ Ouvir Revisão", "callback_data": "/ouvir"}, {"text": "🔍 Perguntar", "callback_data": "modo_pergunta"}],
                    [{"text": "📌 Status", "callback_data": "/status"}, {"text": "💡 Ajuda", "callback_data": "ajuda_bot"}]
                ]
            }
            send_message(chat_id, "📚 <b>Menu Principal</b>\nO que vamos estudar agora?", keyboard)

        # --- AÇÕES DOS BOTÕES DE MENU ---
        elif text == "nova_materia":
            send_message(chat_id, "✍️ Para criar uma matéria, digite:\n/adc NomeDaMateria")

        elif text in ["/ajuda", "ajuda_bot"]:
            ajuda_texto = (
                "💡 <b>Como usar o bot:</b>\n\n"
                "1️⃣ <b>Crie:</b> Digite /adc Nome\n"
                "2️⃣ <b>Selecione:</b> Abra as /materias e escolha o foco\n"
                "3️⃣ <b>Envie:</b> Mande links ou textos soltos\n"
                "4️⃣ <b>Estude:</b> Use o /menu para resumos, quizes ou áudios!"
            )
            send_message(chat_id, ajuda_texto)

        elif text == "modo_pergunta":
            send_message(chat_id, "🧐 <b>Modo Pergunta Ativado!</b>\nDigite <b>/pergunta</b> e sua dúvida.\n\nExemplo: <code>/pergunta O que são juros?</code>")

        # --- O STATUS VOLTOU AQUI ---
        elif text == "/status":
            m = db.query(Materia).get(sessao.materia_ativa) if sessao.materia_ativa else None
            send_message(chat_id, f"📌 Foco atual: <b>{m.nome if m else 'Nenhum'}</b>")

        # --- Comandos de Texto Diretos ---
        elif text.startswith("/adc "):
            nome = text.replace("/adc ", "").strip()
            if nome:
                db.add(Materia(nome=nome, user_id=user.id))
                db.commit()
                send_message(chat_id, f"✅ Matéria <b>{nome}</b> criada!")
            else:
                send_message(chat_id, "⚠️ Digite um nome após o /adc")

        elif text == "listar_materias" or text == "/materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()
            if mats:
                keyboard = {"inline_keyboard": [[{"text": m.nome, "callback_data": f"use_{m.id}"}] for m in mats]}
                send_message(chat_id, "📚 Selecione uma matéria:", keyboard)
            else:
                send_message(chat_id, "📭 Nenhuma matéria. Use /adc Nome")

        elif text.startswith("use_"):
            m_id = int(text.split("_")[1])
            sessao.materia_ativa = m_id; db.commit()
            m = db.query(Materia).get(m_id)
            send_message(chat_id, f"🎯 Foco em: <b>{m.nome}</b>")

        # --- Disparo de Threads (IA, Scraper e VOZ) ---
        elif text in ["/resumir", "/gerar_questoes", "/ouvir"]:
            if sessao.materia_ativa:
                threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, text)).start()
            else:
                send_message(chat_id, "⚠️ Selecione uma matéria.")

        # --- AUTO SAVE ---
        elif not text.startswith("/"):
<<<<<<< Updated upstream
            if sessao.materia_ativa:
                threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, "auto_save", text)).start()
            else:
                send_message(chat_id, "⚠️ Escolha uma matéria primeiro.")

    except Exception as e:
        logger.error(f"Erro: {e}")
    finally:
        db.close()

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)