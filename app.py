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

<<<<<<< Updated upstream
# --- BACKGROUND ---
=======

# ================= MENU GLOBAL =================
def enviar_menu(chat_id):
    keyboard = {
        "inline_keyboard": [
            [{"text": "📚 Matérias", "callback_data": "listar_materias"}, {"text": "➕ Nova", "callback_data": "nova_materia"}],
            [{"text": "📊 Resumir", "callback_data": "/resumir"}, {"text": "📝 Questões", "callback_data": "/gerar_questoes"}],
            [{"text": "🎙️ Ouvir Revisão", "callback_data": "/ouvir"}, {"text": "🔍 Perguntar", "callback_data": "modo_pergunta"}],
            [{"text": "📌 Status", "callback_data": "/status"}, {"text": "💡 Ajuda", "callback_data": "ajuda_bot"}]
        ]
    }

    send_message(chat_id, "📚 <b>Menu Principal</b>\nO que vamos estudar agora?", keyboard)


# --- BACKGROUND TASK PROCESSOR ---
>>>>>>> Stashed changes
def task_processor(chat_id, user_id, sessao_id, action_type, payload=None):
    db = SessionLocal()
    try:
        sessao = db.query(Sessao).get(sessao_id)

        if action_type == "/resumir":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            if materiais:
<<<<<<< Updated upstream
                send_message(chat_id, "🤖 Gerando resumo...")
                texto = " ".join([c.texto for c in materiais])
                res = pedir_ia("Resuma em 5 tópicos curtos.", texto)
                send_message(chat_id, res)

=======
                send_message(chat_id, "🤖 Lendo os últimos materiais e gerando um resumo...")
                materiais.reverse() 
                texto_compilado = "\n\n---\n\n".join([c.texto for c in materiais])
                
                prompt = "Com base no texto fornecido, crie um resumo direto ao ponto em poucos tópicos curtos. Use linguagem simples."
                res = pedir_ia(prompt, texto_compilado)
                
                # Botão para ouvir apenas este resumo
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
            send_message(chat_id, "🎙️ <b>Gravando áudio do resumo...</b>")
            caminho_audio = gerar_audio_do_texto(payload, user_id)
            
            if caminho_audio:
                send_voice(chat_id, caminho_audio)
                if os.path.exists(caminho_audio):
                    os.remove(caminho_audio)
            else:
                send_message(chat_id, "❌ Erro ao gerar áudio.")

        elif action_type == "/ouvir":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).order_by(Conteudo.id.desc()).limit(2).all()
            if materiais:
                send_message(chat_id, "🎙️ <b>Sintetizando revisão...</b>")
                texto_para_voz = "Revisão geral. " + " ".join([c.texto for c in materiais])
                caminho_audio = gerar_audio_do_texto(texto_para_voz, user_id)
                
                if caminho_audio:
                    send_voice(chat_id, caminho_audio)
                    if os.path.exists(caminho_audio):
                        os.remove(caminho_audio)
                else:
                    send_message(chat_id, "❌ Erro ao gerar áudio.")
            else:
                send_message(chat_id, "📭 Sem conteúdo para voz.")

        # ==========================================
        # 3. GERAR QUESTÕES
        # ==========================================
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream

            requests.post(f"{BASE_URL}/answerCallbackQuery", json={
                "callback_query_id": callback["id"]
            })

=======
            mensagem_original_texto = callback["message"].get("text", "") 
            requests.post(f"{BASE_URL}/answerCallbackQuery", json={"callback_query_id": callback["id"]})
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
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
=======
        # Feedbacks
        if text == "feedback_bom":
            send_message(chat_id, "🔥 Ótimo progresso!")
            enviar_menu(chat_id)

        elif text == "feedback_ruim":
            send_message(chat_id, "💪 Foco no erro! Vamos revisar mais isso.")
            enviar_menu(chat_id)

        elif text == "tts_agora":
            threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, "tts_agora", mensagem_original_texto)).start()
            enviar_menu(chat_id)

        # Menu Principal
        elif text in ["/start", "/menu"]:
            enviar_menu(chat_id)

        elif text == "nova_materia":
            send_message(chat_id, "✍️ Para criar uma matéria, digite:\n/adc NomeDaMateria")
            enviar_menu(chat_id)

        elif text == "modo_pergunta":
            send_message(chat_id, "🧐 Use /pergunta sua dúvida")
            enviar_menu(chat_id)

        elif text == "ajuda_bot":
            send_message(chat_id, "💡 Use /adc, /menu e envie conteúdos")
            enviar_menu(chat_id)

        elif text == "/status":
            m = db.query(Materia).get(sessao.materia_ativa) if sessao.materia_ativa else None
            send_message(chat_id, f"📌 Foco atual: <b>{m.nome if m else 'Nenhum'}</b>")
            enviar_menu(chat_id)

        elif text.startswith("/adc "):
            nome = text.replace("/adc ", "").strip()
            if nome:
                db.add(Materia(nome=nome, user_id=user.id))
                db.commit()
                send_message(chat_id, f"✅ Matéria <b>{nome}</b> criada!")
            enviar_menu(chat_id)

        elif text == "listar_materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()
            if mats:
                keyboard = {"inline_keyboard": [[{"text": m.nome, "callback_data": f"use_{m.id}"}] for m in mats]}
                send_message(chat_id, "📚 Selecione uma matéria:", keyboard)
            else:
                send_message(chat_id, "📭 Nenhuma matéria.")
            enviar_menu(chat_id)

        elif text.startswith("use_"):
            m_id = int(text.split("_")[1])
            sessao.materia_ativa = m_id
            db.commit()
            send_message(chat_id, "🎯 Matéria selecionada!")
            enviar_menu(chat_id)

        elif text in ["/resumir", "/gerar_questoes", "/ouvir"]:
            threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, text)).start()
            enviar_menu(chat_id)

        elif text.startswith("/pergunta "):
            threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, "/pergunta", text.replace("/pergunta ",""))).start()
            enviar_menu(chat_id)
>>>>>>> Stashed changes

        elif not text.startswith("/"):
<<<<<<< Updated upstream
            if sessao.materia_ativa:
                threading.Thread(
                    target=task_processor,
                    args=(chat_id, user.id, sessao.id, "auto_save", text)
                ).start()
            else:
                send_message(chat_id, "⚠️ Escolha uma matéria primeiro.")
=======
            threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, "auto_save", text)).start()
            enviar_menu(chat_id)
>>>>>>> Stashed changes

    except Exception as e:
        logger.error(e)
    finally:
        db.close()

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(port=5000)