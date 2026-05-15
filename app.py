import threading
import logging
import requests
from flask import Flask, request, jsonify
from sqlalchemy import text as sqlalchemy_text

from models import SessionLocal, User, Materia, Conteudo, Sessao, engine
from services.telegram import send_message
from services.scraper import extrair_texto_da_url
from services.ai_assistant import pedir_ia
from config import BASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

with engine.connect() as conn:
    conn.execute(sqlalchemy_text("PRAGMA journal_mode=WAL;"))

# --- BACKGROUND ---
def task_processor(chat_id, user_id, sessao_id, action_type, payload=None):
    db = SessionLocal()
    try:
        sessao = db.query(Sessao).get(sessao_id)

        if action_type == "/resumir":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            if materiais:
                send_message(chat_id, "🤖 Gerando resumo...")
                texto = " ".join([c.texto for c in materiais])
                res = pedir_ia("Resuma em 5 tópicos curtos.", texto)
                send_message(chat_id, res)

        elif action_type == "/gerar_questoes":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            if materiais:
                send_message(chat_id, "🤖 Gerando questões...")
                texto = " ".join([c.texto for c in materiais])
                res = pedir_ia("Crie 3 questões com gabarito.", texto)
                send_message(chat_id, res)

        elif action_type == "auto_save":
            if payload.startswith("http"):
                send_message(chat_id, "🌐 Processando link...")
                texto = extrair_texto_da_url(payload)
                tipo = "link"
            else:
                texto = payload
                tipo = "texto"

            if texto:
                db.add(Conteudo(texto=texto, tipo=tipo, materia_id=sessao.materia_ativa))
                db.commit()
                send_message(chat_id, "✅ Conteúdo salvo.")

    except Exception as e:
        logger.error(e)
        send_message(chat_id, "❌ Erro.")
    finally:
        db.close()

# --- WEBHOOK ---
@app.route("/webhook", methods=["POST"])
def webhook():
    db = SessionLocal()

    try:
        data = request.json

        # --- BOTÕES ---
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

        # --- USER ---
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

        # --- MENU ---
        if text in ["/start", "/menu"]:
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "📊 Resumir", "callback_data": "/resumir"},
                        {"text": "❓ Questões", "callback_data": "/gerar_questoes"}
                    ],
                    [
                        {"text": "➕ Nova Matéria", "callback_data": "nova_materia"},
                        {"text": "📚 Ver Matérias", "callback_data": "listar_materias"}
                    ],
                    [
                        {"text": "📌 Status", "callback_data": "/status"}
                    ]
                ]
            }

            send_message(chat_id, "📚 <b>Menu</b>", keyboard)

        # --- NOVA MATÉRIA ---
        elif text == "nova_materia":
            send_message(chat_id, "✍️ Digite:\n/add NomeDaMateria")

        # --- LISTAR MATÉRIAS COM BOTÃO ---
        elif text == "listar_materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()

            if mats:
                keyboard = {
                    "inline_keyboard": [
                        [{"text": m.nome, "callback_data": f"use_{m.id}"}]
                        for m in mats
                    ]
                }

                send_message(chat_id, "📚 Escolha uma matéria:", keyboard)
            else:
                send_message(chat_id, "📭 Nenhuma matéria.")

        # --- USAR MATÉRIA VIA BOTÃO ---
        elif text.startswith("use_"):
            materia_id = int(text.split("_")[1])
            sessao.materia_ativa = materia_id
            db.commit()

            m = db.query(Materia).get(materia_id)
            send_message(chat_id, f"🎯 Matéria ativa: {m.nome}")

        # --- STATUS ---
        elif text == "/status":
            m = db.query(Materia).get(sessao.materia_ativa) if sessao.materia_ativa else None
            send_message(chat_id, f"📖 Atual: {m.nome if m else 'Nenhuma'}")

        # --- ADD MATÉRIA ---
        elif text.startswith("/add"):
            nome = text.replace("/add", "").strip()
            if nome:
                db.add(Materia(nome=nome, user_id=user.id))
                db.commit()
                send_message(chat_id, f"✅ Criada: {nome}")

        # --- IA ---
        elif text in ["/resumir", "/gerar_questoes"]:
            if sessao.materia_ativa:
                threading.Thread(
                    target=task_processor,
                    args=(chat_id, user.id, sessao.id, text)
                ).start()
            else:
                send_message(chat_id, "⚠️ Selecione uma matéria.")

        # --- AUTO SAVE ---
        elif not text.startswith("/"):
            if sessao.materia_ativa:
                threading.Thread(
                    target=task_processor,
                    args=(chat_id, user.id, sessao.id, "auto_save", text)
                ).start()
            else:
                send_message(chat_id, "⚠️ Escolha uma matéria primeiro.")

    except Exception as e:
        logger.error(e)
    finally:
        db.close()

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=5000)