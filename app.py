from flask import Flask, request
import logging
from models import SessionLocal, User, Materia, Conteudo, Sessao
from services.telegram import send_message
from services.scraper import extrair_texto_da_url
from services.ai_assistant import pedir_ia

app = Flask(__name__)

# Configuração de Log para você ver o erro real no terminal
logging.basicConfig(level=logging.INFO)

def get_session_data(db, chat_id):
    user = db.query(User).filter_by(telegram_id=str(chat_id)).first()
    if not user:
        user = User(telegram_id=str(chat_id))
        db.add(user)
        db.commit()
    
    sessao = db.query(Sessao).filter_by(user_id=user.id).first()
    if not sessao:
        sessao = Sessao(user_id=user.id)
        db.add(sessao)
        db.commit()
    return user, sessao

@app.route("/webhook", methods=["POST"])
def webhook():
    db = SessionLocal()
    try:
        data = request.json
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text") # Removido o padrão "" para detectar se é texto

        if not chat_id or not text:
            return {"ok": True}

        user, sessao = get_session_data(db, chat_id)

        # --- MENU ---
        if text in ["/start", "/menu"]:
            menu = (
                "📚 ASSISTENTE DE ESTUDOS\n\n"
                "/add Nome - Criar materia\n"
                "/materias - Minhas materias\n"
                "/use Nome - Selecionar materia\n"
                "/status - Ver materia atual\n\n"
                "📝 CONTEUDO\n"
                "Envie texto ou link para salvar\n\n"
                "🤖 IA\n"
                "/resumir | /gerar_questoes"
            )
            send_message(chat_id, menu)

        elif text == "/status":
            if not sessao.materia_ativa:
                send_message(chat_id, "Nenhuma materia selecionada. Use: /use Nome")
            else:
                m = db.query(Materia).filter_by(id=sessao.materia_ativa).first()
                nome_materia = m.nome if m else "Desconhecida"
                send_message(chat_id, f"📖 Materia atual: {nome_materia}")

        elif text.startswith("/add"):
            nome = text.replace("/add", "").strip()
            if nome:
                m = Materia(nome=nome, user_id=user.id)
                db.add(m)
                db.commit()
                send_message(chat_id, f"✅ {nome} criada!")
            else:
                send_message(chat_id, "Digite: /add Nome")

        elif text == "/materias":
            materias = db.query(Materia).filter_by(user_id=user.id).all()
            if not materias:
                send_message(chat_id, "Vazio. Crie com /add")
            else:
                # LISTA INCREMENTAL (1, 2, 3...)
                lista = [f"{i+1}. {m.nome}" for i, m in enumerate(materias)]
                send_message(chat_id, "Suas materias:\n\n" + "\n".join(lista))

        elif text.startswith("/use"):
            nome_busca = text.replace("/use", "").strip()
            materia = db.query(Materia).filter_by(user_id=user.id, nome=nome_busca).first()
            if materia:
                sessao.materia_ativa = materia.id
                db.commit()
                send_message(chat_id, f"🎯 Focado em: {materia.nome}")
            else:
                send_message(chat_id, "Materia nao encontrada.")

        elif text == "/resumir":
            if not sessao.materia_ativa:
                send_message(chat_id, "Use /use primeiro.")
            else:
                conts = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
                if conts:
                    send_message(chat_id, "🤖 Resumindo com Groq...")
                    texto_total = " ".join([c.texto for c in conts])
                    res = pedir_ia("Resumo curto em tópicos.", texto_total)
                    send_message(chat_id, res)
                else:
                    send_message(chat_id, "Materia sem conteudo.")

        elif text == "/gerar_questoes":
            if not sessao.materia_ativa:
                send_message(chat_id, "Use /use primeiro.")
            else:
                conts = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
                if conts:
                    send_message(chat_id, "🤖 Criando questões...")
                    texto_total = " ".join([c.texto for c in conts])
                    res = pedir_ia("Crie 3 perguntas com respostas.", texto_total)
                    send_message(chat_id, res)

        # SALVAR AUTOMÁTICO
        elif not text.startswith("/"):
            if not sessao.materia_ativa:
                send_message(chat_id, "Selecione uma materia com /use primeiro.")
            else:
                if text.startswith("http"):
                    send_message(chat_id, "🌐 Lendo link...")
                    final = extrair_texto_da_url(text)
                    tipo = "link"
                else:
                    final = text
                    tipo = "texto"
                
                if final:
                    c = Conteudo(texto=final, tipo=tipo, materia_id=sessao.materia_ativa)
                    db.add(c)
                    db.commit()
                    send_message(chat_id, "✅ Conteúdo salvo!")

    except Exception as e:
        app.logger.error(f"ERRO NO WEBHOOK: {e}")
        # Retornamos 200 mesmo no erro para o Telegram parar de reenviar a mesma mensagem
        return {"ok": False, "error": str(e)}, 200
    finally:
        db.close() # ESSENCIAL: Fecha a conexão com o banco sempre

    return {"ok": True}

if __name__ == "__main__":
    app.run(port=5000, debug=True)