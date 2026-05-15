import threading
import logging
import random
import requests
import os
from flask import Flask, request, jsonify
from sqlalchemy import text as sqlalchemy_text

# NOVO IMPORT (PDF)
from pypdf import PdfReader

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

# ==========================================
# MENU PADRÃO (REUTILIZÁVEL)
# ==========================================
def menu_padrao():
    return {
        "inline_keyboard": [
            [{"text": "📚 Matérias", "callback_data": "listar_materias"}, {"text": "➕ Nova", "callback_data": "nova_materia"}],
            [{"text": "📊 Resumir", "callback_data": "/resumir"}, {"text": "📝 Questões", "callback_data": "/gerar_questoes"}],
            [{"text": "🎙️ Ouvir Revisão", "callback_data": "/ouvir"}, {"text": "🔍 Perguntar", "callback_data": "modo_pergunta"}],
            [{"text": "📌 Status", "callback_data": "/status"}, {"text": "💡 Ajuda", "callback_data": "ajuda_bot"}]
        ]
    }

# ==========================================
# FUNÇÕES DE PDF
# ==========================================
def baixar_pdf(file_id):
    res = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
    file_path = res["result"]["file_path"]

    token = BASE_URL.split("bot")[1]
    url = f"https://api.telegram.org/file/bot{token}/{file_path}"

    caminho = f"/tmp/{file_id}.pdf"

    r = requests.get(url)
    with open(caminho, "wb") as f:
        f.write(r.content)

    return caminho

def extrair_texto_pdf(caminho):
    reader = PdfReader(caminho)
    texto = ""

    for page in reader.pages:
        texto += page.extract_text() or ""

    return texto

def processar_pdf(chat_id, user_id, sessao_id, file_id):
    try:
        send_message(chat_id, "📄 Baixando PDF...", menu_padrao())

        caminho = baixar_pdf(file_id)

        send_message(chat_id, "📖 Lendo conteúdo...", menu_padrao())

        texto = extrair_texto_pdf(caminho)

        if not texto.strip():
            send_message(chat_id, "❌ Não consegui ler esse PDF.", menu_padrao())
            return

        send_message(chat_id, "🤖 Gerando resumo...", menu_padrao())

        resumo = pedir_ia(
            "Resuma em tópicos curtos e diretos.",
            texto[:12000]
        )

        send_message(chat_id, resumo, menu_padrao())

        os.remove(caminho)

    except Exception as e:
        send_message(chat_id, f"❌ Erro no PDF: {e}", menu_padrao())

# --- BACKGROUND ---
def task_processor(chat_id, user_id, sessao_id, action_type, payload=None):
    db = SessionLocal()
    try:
        sessao = db.query(Sessao).get(sessao_id)

        if not sessao or not sessao.materia_ativa:
            send_message(chat_id, "⚠️ Nenhuma matéria ativa.", menu_padrao())
            return

        if action_type == "/resumir":
            materiais = db.query(Conteudo)\
                          .filter_by(materia_id=sessao.materia_ativa)\
                          .order_by(Conteudo.id.desc())\
                          .limit(5).all()
            
            if materiais:
                send_message(chat_id, "🤖 Gerando resumo...", menu_padrao())
                texto = " ".join([c.texto for c in materiais])
                res = pedir_ia("Resuma em tópicos curtos.", texto)

                keyboard = {
                    "inline_keyboard": [[
                        {"text": "🔊 Ouvir", "callback_data": "tts_agora"}
                    ]]
                }

                send_message(chat_id, res, keyboard)
            else:
                send_message(chat_id, "📭 Sem conteúdo.", menu_padrao())

        elif action_type == "tts_agora":
            caminho_audio = gerar_audio_do_texto(payload, user_id)
            if caminho_audio:
                send_voice(chat_id, caminho_audio)
                os.remove(caminho_audio)

        elif action_type == "/gerar_questoes":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            if materiais:
                send_message(chat_id, "🤖 Criando questões...", menu_padrao())
                texto = " ".join([c.texto for c in materiais])
                res = pedir_ia("Crie 3 questões com gabarito oculto.", texto)
                send_message(chat_id, res, menu_padrao())

        elif action_type == "auto_save":
            texto = payload
            pedacos = chunk_text(texto, 1000, 100)
            for p in pedacos:
                db.add(Conteudo(texto=p, tipo="texto", materia_id=sessao.materia_ativa))
            db.commit()
            send_message(chat_id, "✅ Salvo!", menu_padrao())

    except Exception as e:
        logger.error(e)
    finally:
        db.close()

# --- WEBHOOK ---
@app.route("/webhook", methods=["POST"])
def webhook():
    db = SessionLocal()
    try:
        data = request.json

        # CALLBACK
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

            # ==========================================
            # DETECÇÃO DE PDF
            # ==========================================
            document = msg.get("document")
            if document and document.get("mime_type") == "application/pdf":
                file_id = document.get("file_id")

                threading.Thread(
                    target=processar_pdf,
                    args=(chat_id, None, None, file_id)
                ).start()

                return jsonify({"status": "ok"}), 200

        if not chat_id or not text:
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
            send_message(chat_id, "📚 Menu Principal", menu_padrao())

        elif text == "nova_materia":
            send_message(chat_id, "Use: /adc Nome", menu_padrao())

        elif text.startswith("/adc "):
            nome = text.replace("/adc ", "").strip()
            db.add(Materia(nome=nome, user_id=user.id))
            db.commit()
            send_message(chat_id, f"✅ {nome} criada!", menu_padrao())

        elif text == "listar_materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()
            keyboard = {"inline_keyboard": [[{"text": m.nome, "callback_data": f"use_{m.id}"}] for m in mats]}
            send_message(chat_id, "Escolha:", keyboard)

        elif text.startswith("use_"):
            m_id = int(text.split("_")[1])
            sessao.materia_ativa = m_id
            db.commit()
            send_message(chat_id, "🎯 Matéria selecionada!", menu_padrao())

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
    app.run(host="0.0.0.0", port=5000)