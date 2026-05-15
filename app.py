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
from services.pdf_reader import extrair_texto_pdf  # 🔥 NOVO
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
                
                prompt = "Com base no texto fornecido, crie um resumo direto ao ponto em poucos tópicos curtos."
                res = pedir_ia(prompt, texto_compilado)
                
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
            send_message(chat_id, "🎙️ Gravando áudio...")
            caminho_audio = gerar_audio_do_texto(payload, user_id)
            
            if caminho_audio:
                send_voice(chat_id, caminho_audio)
                if os.path.exists(caminho_audio):
                    os.remove(caminho_audio)
            else:
                send_message(chat_id, "❌ Erro ao gerar áudio.")

        # ==========================================
        # 3. GERAR QUESTÕES
        # ==========================================
        elif action_type == "/gerar_questoes":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            
            if materiais:
                send_message(chat_id, "🤖 Preparando seu teste...")
                amostra = random.sample(materiais, min(len(materiais), 4))
                texto_compilado = "\n\n---\n\n".join([c.texto for c in amostra])
                
                prompt = "Crie 3 questões de múltipla escolha com gabarito oculto."
                res = pedir_ia(prompt, texto_compilado)
                
                send_message(chat_id, res)
            else:
                send_message(chat_id, "📭 A matéria está vazia.")

        # ==========================================
        # 4. RESPONDER DÚVIDAS
        # ==========================================
        elif action_type == "/pergunta":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            if materiais:
                texto_compilado = "\n\n".join([c.texto for c in materiais[-5:]])
                prompt = f"Pergunta: {payload}"
                res = pedir_ia(prompt, texto_compilado)
                send_message(chat_id, res)

        # ==========================================
        # 5. PROCESSAR PDF (🔥 NOVO COMPLETO)
        # ==========================================
        elif action_type == "pdf":
            send_message(chat_id, "📄 Lendo PDF...")

            texto = extrair_texto_pdf(payload)

            if not texto:
                send_message(chat_id, "❌ Não consegui ler o PDF.")
                return

            # 🔥 CHUNKING
            pedacos = chunk_text(texto, max_chars=1000, overlap=100)

            for p in pedacos:
                db.add(Conteudo(
                    texto=p,
                    tipo="pdf",
                    materia_id=sessao.materia_ativa
                ))

            db.commit()

            send_message(chat_id, f"✅ PDF salvo em {len(pedacos)} partes!")

            # 🔥 RESUMO AUTOMÁTICO
            resumo = pedir_ia("Resuma em poucos tópicos:", texto[:5000])
            send_message(chat_id, resumo)

            # remove arquivo
            if os.path.exists(payload):
                os.remove(payload)

        # ==========================================
        # 6. AUTO SAVE
        # ==========================================
        elif action_type == "auto_save":
            if payload.startswith("http"):
                texto = extrair_texto_da_url(payload)
                tipo = "link"
            else:
                texto = payload
                tipo = "texto"

            if texto:
                pedacos = chunk_text(texto, max_chars=1000, overlap=100)
                for p in pedacos:
                    db.add(Conteudo(texto=p, tipo=tipo, materia_id=sessao.materia_ativa))
                db.commit()
                send_message(chat_id, "✅ Conteúdo salvo!")

    except Exception as e:
        logger.error(f"Erro: {e}")
        send_message(chat_id, "❌ Erro.")
    finally:
        db.close()


# --- WEBHOOK ---
@app.route("/webhook", methods=["POST"])
def webhook():
    db = SessionLocal()
    try:
        data = request.json

        if "message" not in data:
            return jsonify({"status": "ok"}), 200

        msg = data["message"]
        chat_id = msg["chat"]["id"]

        # ==========================================
        # 📄 RECEBER PDF
        # ==========================================
        if "document" in msg:
            file_id = msg["document"]["file_id"]

            # pegar arquivo
            file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]

            file_url = f"https://api.telegram.org/file/bot{BASE_URL.split('bot')[1]}/{file_path}"

            caminho_local = f"temp_{file_id}.pdf"

            with open(caminho_local, "wb") as f:
                f.write(requests.get(file_url).content)

            user = db.query(User).filter_by(telegram_id=str(chat_id)).first()
            sessao = db.query(Sessao).filter_by(user_id=user.id).first()

            threading.Thread(
                target=task_processor,
                args=(chat_id, user.id, sessao.id, "pdf", caminho_local)
            ).start()

            return jsonify({"status": "ok"}), 200

        text = msg.get("text")

        if not text:
            return jsonify({"status": "ok"}), 200

        user = db.query(User).filter_by(telegram_id=str(chat_id)).one_or_none()
        if not user:
            user = User(telegram_id=str(chat_id))
            db.add(user); db.commit(); db.refresh(user)

        sessao = db.query(Sessao).filter_by(user_id=user.id).one_or_none()
        if not sessao:
            sessao = Sessao(user_id=user.id)
            db.add(sessao); db.commit(); db.refresh(sessao)

        # MENU
        if text in ["/start", "/menu"]:
            send_message(chat_id, "📚 Menu ativo")

        elif text.startswith("/adc "):
            nome = text.replace("/adc ", "")
            db.add(Materia(nome=nome, user_id=user.id))
            db.commit()
            send_message(chat_id, "✅ Criada")

        elif text == "/materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()
            lista = "\n".join([m.nome for m in mats])
            send_message(chat_id, lista or "Vazio")

        elif text.startswith("/use "):
            nome = text.replace("/use ", "")
            m = db.query(Materia).filter_by(user_id=user.id, nome=nome).first()
            if m:
                sessao.materia_ativa = m.id
                db.commit()
                send_message(chat_id, "🎯 Selecionada")

        elif text in ["/resumir", "/gerar_questoes"]:
            threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, text)).start()

        elif not text.startswith("/"):
            threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, "auto_save", text)).start()

    except Exception as e:
        logger.error(e)
    finally:
        db.close()

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=5000)