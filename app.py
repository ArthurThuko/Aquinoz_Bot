import logging
from flask import Flask, request, jsonify
from sqlalchemy import text as sqlalchemy_text
from models import engine
from controllers.telegram_handler import processar_mensagem
# Importamos a função que lida com o feedback educacional
from tasks.study import processar_resposta_desafio

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

        # MENSAGEM COMUM (Texto, PDF, Links, etc.)
        if "message" in data:
            processar_mensagem(data["message"])
        
        # CLIQUE NAS BOLHAS (BOTÕES INLINE)
        elif "callback_query" in data:
            callback = data["callback_query"]
            callback_data = callback.get("data", "")

            # 🧠 INTERCEPTOR DO DESAFIO (Sincronizado com o seu study.py)
            if callback_data.startswith("/chk_"):
                # Destrincha exatamente as 5 partes: ['/chk', 'materia', 'pagina', 'escolha', 'gabarito']
                partes = callback_data.split("_")
                materia_id = int(partes[1])
                proxima_pagina = int(partes[2])
                escolha = partes[3]   # O botão que o aluno clicou (A ou B)
                gabarito = partes[4]  # O gabarito correto que a IA escondeu (A ou B)
                chat_id = callback["message"]["chat"]["id"]

                # Dispara enviando todos os parâmetros que o seu study.py precisa
                processar_resposta_desafio(chat_id, materia_id, proxima_pagina, escolha, gabarito)
            
            else:
                # O SEU COMPORTAMENTO ORIGINAL: Mantém o fluxo antigo para o áudio e outros botões
                msg_fake = {
                    "chat": callback["message"]["chat"],
                    "text": callback_data, 
                    "conteudo_da_bolha": callback["message"].get("text", ""), 
                    "from": callback["from"]
                }
                processar_mensagem(msg_fake)

    except Exception as e:
        logger.error(f"Erro no webhook: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(port=5000)