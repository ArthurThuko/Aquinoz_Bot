import threading
import logging
import random
import requests
from flask import Flask, request, jsonify
from sqlalchemy import text as sqlalchemy_text

# Importações dos seus modelos e banco
from models import SessionLocal, User, Materia, Conteudo, Sessao, engine

# Importações dos seus serviços
from services.telegram import send_message
from services.scraper import extrair_texto_da_url
from services.ai_assistant import pedir_ia
from services.chunker import chunk_text
from config import BASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuração de performance do SQLite
with engine.connect() as conn:
    conn.execute(sqlalchemy_text("PRAGMA journal_mode=WAL;"))


# --- BACKGROUND TASK PROCESSOR ---
def task_processor(chat_id, user_id, sessao_id, action_type, payload=None):
    db = SessionLocal()
    try:
        sessao = db.query(Sessao).get(sessao_id)

        if not sessao or not sessao.materia_ativa:
            send_message(chat_id, "⚠️ Nenhuma matéria ativa. Por favor, selecione uma no menu.")
            return

        # ==========================================
        # 1. GERAR RESUMO
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
                send_message(chat_id, res)
            else:
                send_message(chat_id, "📭 A matéria está vazia. Envie textos ou links primeiro.")

        # ==========================================
        # 2. GERAR QUESTÕES (Com Spoilers e Feedback)
        # ==========================================
        elif action_type == "/gerar_questoes":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            
            if materiais:
                send_message(chat_id, "🤖 Sorteando trechos e blindando suas questões contra trapaça...")
                amostra = random.sample(materiais, min(len(materiais), 4))
                texto_compilado = "\n\n---\n\n".join([c.texto for c in amostra])
                
                prompt = (
                    "Use o conteúdo fornecido para criar 3 questões de múltipla escolha (A, B, C, D).\n"
                    "Faça perguntas que exijam raciocínio, não apenas decoreba.\n\n"
                    "REGRA CRÍTICA DE FORMATAÇÃO DO TELEGRAM:\n"
                    "As alternativas (A, B, C, D) devem ficar visíveis normalmente.\n"
                    "Você DEVE ocultar APENAS a resposta final usando a tag <tg-spoiler>.\n"
                    "Siga EXATAMENTE este modelo de estrutura:\n\n"
                    "1) Qual o conceito de juros?\n"
                    "A) Texto da alternativa A aqui\n"
                    "B) Texto da alternativa B aqui\n"
                    "C) Texto da alternativa C aqui\n"
                    "D) Texto da alternativa D aqui\n\n"
                    "Gabarito: <tg-spoiler>Letra X - Explicação da resposta certa aqui.</tg-spoiler>"
                )
                
                res = pedir_ia(prompt, texto_compilado)
                
                keyboard_feedback = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Acertei!", "callback_data": "feedback_bom"},
                            {"text": "❌ Errei/Dificuldade", "callback_data": "feedback_ruim"}
                        ]
                    ]
                }
                send_message(chat_id, res, keyboard_feedback)
            else:
                send_message(chat_id, "📭 A matéria está vazia. Envie textos ou links primeiro.")

        # ==========================================
        # 3. RESPONDER DÚVIDAS (Modo Pergunta)
        # ==========================================
        elif action_type == "/pergunta":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            
            if materiais:
                send_message(chat_id, "🔍 Vasculhando seus materiais salvos para encontrar a resposta...")
                
                # Contexto extraído dos últimos 5 blocos salvos
                texto_compilado = "\n\n---\n\n".join([c.texto for c in materiais[-5:]])
                
                prompt = (
                    f"Você é um tutor de estudos amigável. O usuário fez a seguinte pergunta: '{payload}'\n\n"
                    f"Instruções:\n"
                    f"1. Responda APENAS E ESTRITAMENTE com base no texto fornecido.\n"
                    f"2. Se a resposta para a pergunta NÃO ESTIVER no texto, ou se for um assunto totalmente desconexo, "
                    f"você está PROIBIDO de inventar. Responda EXATAMENTE com esta frase:\n"
                    f"'Não tenho dados sobre esse assunto, mas caso você queira saber mais, pode me mandar links ou textos que eu criarei questões para ajudar.'\n"
                    f"3. Caso a resposta esteja no texto, seja direto e use linguagem simples."
                )
                
                # Garantindo o envio do prompt E do contexto
                res = pedir_ia(prompt, texto_compilado)
                send_message(chat_id, res)
            else:
                send_message(chat_id, "📭 A matéria está vazia. Envie textos ou links primeiro.")

        # ==========================================
        # 4. AUTO SAVE COM CHUNKING
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
                    novo_conteudo = Conteudo(
                        texto=pedaco, 
                        tipo=tipo, 
                        materia_id=sessao.materia_ativa
                    )
                    db.add(novo_conteudo)
                
                db.commit()
                send_message(chat_id, f"✅ Material salvo! Dividido em {len(pedacos)} blocos de conhecimento.")
            else:
                send_message(chat_id, "⚠️ Não consegui extrair informações úteis desse envio.")

    except Exception as e:
        import traceback
        erro_real = traceback.format_exc()
        logger.error(f"Erro no processamento da task: \n{erro_real}")
        send_message(chat_id, f"❌ <b>Erro interno:</b>\n<code>{str(e)}</code>")
    finally:
        db.close()


# --- WEBHOOK ---
@app.route("/webhook", methods=["POST"])
def webhook():
    db = SessionLocal()

    try:
        data = request.json

        # --- Tratamento de Botões Inline ---
        if "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["message"]["chat"]["id"]
            text = callback["data"]

            requests.post(f"{BASE_URL}/answerCallbackQuery", json={
                "callback_query_id": callback["id"]
            })

        # --- Tratamento de Mensagens Normais ---
        else:
            msg = data.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text")

        if not chat_id or not text:
            return jsonify({"status": "ok"}), 200

        # --- Gerenciamento de Usuário e Sessão ---
        user = db.query(User).filter_by(telegram_id=str(chat_id)).one_or_none()
        if not user:
            user = User(telegram_id=str(chat_id))
            db.add(user)
            db.commit()
            db.refresh(user)

        sessao = db.query(Sessao).filter_by(user_id=user.id).one_or_none()
        if not sessao:
            sessao = Sessao(user_id=user.id)
            db.add(sessao)
            db.commit()
            db.refresh(sessao)

        # --- Tratamento de Feedbacks das Questões ---
        if text == "feedback_bom":
            send_message(chat_id, "🔥 Excelente! Você está dominando esse assunto. Continue assim!")
            return jsonify({"status": "ok"}), 200
            
        elif text == "feedback_ruim":
            send_message(chat_id, "💪 Sem problemas, errar faz parte! Vou priorizar esse assunto nos seus próximos resumos e testes.")
            return jsonify({"status": "ok"}), 200

        # --- Roteamento de Comandos (Menu Reorganizado) ---
        if text in ["/start", "/menu"]:
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📚 Minhas Matérias", "callback_data": "listar_materias"},
                        {"text": "➕ Nova Matéria", "callback_data": "nova_materia"}
                    ],
                    [
                        {"text": "📊 Resumir", "callback_data": "/resumir"},
                        {"text": "📝 Questões", "callback_data": "/gerar_questoes"}
                    ],
                    [
                        {"text": "🔍 Perguntar", "callback_data": "modo_pergunta"},
                        {"text": "📌 Status", "callback_data": "/status"}
                    ],
                    [
                        {"text": "💡 Como Usar (Ajuda)", "callback_data": "ajuda_bot"}
                    ]
                ]
            }
            send_message(chat_id, "📚 <b>Menu Principal</b>\nEscolha uma ação abaixo:", keyboard)

        # --- SISTEMA DE AJUDA ---
        elif text in ["/ajuda", "ajuda_bot"]:
            ajuda_texto = (
                "💡 <b>Como usar o bot passo a passo:</b>\n\n"
                "<b>1️⃣ Crie uma matéria:</b>\n"
                "Use o botão <i>➕ Nova Matéria</i> ou digite direto: <code>/add NomeDaMateria</code>\n\n"
                "<b>2️⃣ Selecione a matéria:</b>\n"
                "Vá em <i>📚 Minhas Matérias</i> e clique na que você criou.\n\n"
                "<b>3️⃣ Alimente o cérebro do bot:</b>\n"
                "Com a matéria ativa, basta enviar textos longos, anotações ou links da internet direto no chat. Eu vou fatiar e organizar tudo!\n\n"
                "<b>4️⃣ Estude e Revise:</b>\n"
                "Sempre que quiser estudar, abra o <b>/menu</b> e escolha:\n"
                "• <b>📊 Resumir:</b> Cria um resumo rápido dos últimos textos salvos.\n"
                "• <b>📝 Questões:</b> Gera um teste para blindar seu conhecimento.\n"
                "• <b>🔍 Perguntar:</b> Vasculha seus envios para responder dúvidas específicas."
            )
            send_message(chat_id, ajuda_texto)

        # --- AÇÕES DA MATÉRIA ---
        elif text == "nova_materia":
            send_message(chat_id, "✍️ Para criar uma matéria, digite:\n/add NomeDaMateria")

        elif text == "listar_materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()
            if mats:
                keyboard = {
                    "inline_keyboard": [
                        [{"text": m.nome, "callback_data": f"use_{m.id}"}]
                        for m in mats
                    ]
                }
                send_message(chat_id, "📚 Escolha a matéria que deseja estudar:", keyboard)
            else:
                send_message(chat_id, "📭 Nenhuma matéria cadastrada.")

        elif text.startswith("use_"):
            materia_id = int(text.split("_")[1])
            sessao.materia_ativa = materia_id
            db.commit()
            m = db.query(Materia).get(materia_id)
            send_message(chat_id, f"🎯 Matéria ativa configurada para: <b>{m.nome}</b>\n\nAgora você pode enviar textos/links ou abrir o /menu.")

        elif text == "/status":
            m = db.query(Materia).get(sessao.materia_ativa) if sessao.materia_ativa else None
            send_message(chat_id, f"📖 Matéria atual em foco: <b>{m.nome if m else 'Nenhuma'}</b>")

        elif text.startswith("/add"):
            nome = text.replace("/add", "").strip()
            if nome:
                db.add(Materia(nome=nome, user_id=user.id))
                db.commit()
                send_message(chat_id, f"✅ Matéria <b>{nome}</b> criada com sucesso!\n\nAbra o /menu e clique em <i>📚 Minhas Matérias</i> para selecioná-la.")
                
        elif text == "modo_pergunta":
            if sessao.materia_ativa:
                tem_conteudo = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).first()
                if tem_conteudo:
                    send_message(chat_id, "🧐 <b>Modo Pergunta Ativado!</b>\nPara perguntar, digite <b>/pergunta</b> e sua dúvida na frente.\n\nExemplo:\n<code>/pergunta O que são juros compostos?</code>")
                else:
                    send_message(chat_id, "📭 <b>Matéria vazia!</b>\nVocê ainda não enviou nenhum conteúdo para esta matéria.\n\nEnvie textos ou links primeiro para que eu possa responder suas dúvidas.")
            else:
                send_message(chat_id, "⚠️ Você precisa selecionar uma matéria antes de fazer perguntas.\n\nClique em <b>📚 Minhas Matérias</b> no menu para escolher uma.")

        # --- Disparo de Tarefas em Background (Thread) ---
        elif text.startswith("/pergunta "):
            duvida = text.replace("/pergunta ", "").strip()
            if sessao.materia_ativa:
                threading.Thread(
                    target=task_processor,
                    args=(chat_id, user.id, sessao.id, "/pergunta", duvida)
                ).start()
            else:
                send_message(chat_id, "⚠️ Escolha uma matéria primeiro.")

        elif text in ["/resumir", "/gerar_questoes"]:
            if sessao.materia_ativa:
                threading.Thread(
                    target=task_processor,
                    args=(chat_id, user.id, sessao.id, text)
                ).start()
            else:
                send_message(chat_id, "⚠️ Selecione uma matéria.")

        # --- AUTO SAVE (Mensagens normais sem barra "/") ---
        elif not text.startswith("/"):
            if sessao.materia_ativa:
                threading.Thread(
                    target=task_processor,
                    args=(chat_id, user.id, sessao.id, "auto_save", text)
                ).start()
            else:
                send_message(chat_id, "⚠️ Escolha uma matéria primeiro.")

    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
    finally:
        db.close()

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(port=5000)