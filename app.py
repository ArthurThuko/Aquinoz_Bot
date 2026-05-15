from flask import Flask, request
from models import SessionLocal, User, Materia, Conteudo, Sessao
from services.telegram import send_message

app = Flask(__name__)

def get_or_create_user(db, telegram_id):
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)
        db.commit()
    return user

def get_session(db, user_id):
    sessao = db.query(Sessao).filter_by(user_id=user_id).first()
    if not sessao:
        sessao = Sessao(user_id=user_id)
        db.add(sessao)
        db.commit()
    return sessao

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    message = data.get("message", {})

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    db = SessionLocal()
    user = get_or_create_user(db, str(chat_id))
    sessao = get_session(db, user.id)

    # ========================
    # COMANDOS
    # ========================

    if text == "/start":
        send_message(chat_id, "Bot iniciado. Use /nova_materia")

    elif text.startswith("/nova_materia"):
        nome = text.replace("/nova_materia", "").strip()

        if not nome:
            send_message(chat_id, "Digite: /nova_materia NomeDaMateria")
        else:
            materia = Materia(nome=nome, user_id=user.id)
            db.add(materia)
            db.commit()

            send_message(chat_id, f"Matéria '{nome}' criada!")

    elif text == "/ver_materias":
        materias = db.query(Materia).filter_by(user_id=user.id).all()

        if not materias:
            send_message(chat_id, "Nenhuma matéria cadastrada.")
        else:
            resposta = "Matérias:\n"
            for m in materias:
                resposta += f"{m.id} - {m.nome}\n"

            send_message(chat_id, resposta)

    elif text.startswith("/selecionar_materia"):
        try:
            materia_id = int(text.split(" ")[1])
            sessao.materia_ativa = materia_id
            db.commit()

            send_message(chat_id, "Matéria selecionada!")
        except:
            send_message(chat_id, "Use: /selecionar_materia ID")

    elif text.startswith("/adicionar_texto"):
        if not sessao.materia_ativa:
            send_message(chat_id, "Selecione uma matéria primeiro.")
        else:
            conteudo_texto = text.replace("/adicionar_texto", "").strip()

            conteudo = Conteudo(
                texto=conteudo_texto,
                tipo="texto",
                materia_id=sessao.materia_ativa
            )

            db.add(conteudo)
            db.commit()

            send_message(chat_id, "Texto salvo com sucesso!")

    else:
        send_message(chat_id, "Comando não reconhecido.")

    return {"ok": True}

if __name__ == "__main__":
    app.run(port=5000)