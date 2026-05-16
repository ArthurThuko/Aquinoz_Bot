import logging
from flask import Flask, request, jsonify
from sqlalchemy import text as sqlalchemy_text
from models import engine
from bot_handler import processar_mensagem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

with engine.connect() as conn:
    conn.execute(sqlalchemy_text("PRAGMA journal_mode=WAL;"))

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "ok"}), 200

        # MENSAGEM COMUM
        if "message" in data:
            processar_mensagem(data["message"])
        
        # CLIQUE NAS BOLHAS (BOTÕES INLINE)
        elif "callback_query" in data:
            callback = data["callback_query"]
            # A MÁGICA DO ÁUDIO: Pegamos o texto que estava acima do botão clicado
            msg_fake = {
                "chat": callback["message"]["chat"],
                "text": callback["data"], # O comando (ex: /audio_resumo)
                "conteudo_da_bolha": callback["message"].get("text", ""), # O resumo em si!
                "from": callback["from"]
            }
            processar_mensagem(msg_fake)

    except Exception as e:
        logger.error(f"Erro no webhook: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(port=5000)