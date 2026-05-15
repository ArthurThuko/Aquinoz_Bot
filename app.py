import threading
import logging
from flask import Flask, request, jsonify
from sqlalchemy import text as sqlalchemy_text

# Imports de Domínio e Infraestrutura
from models import SessionLocal, User, Materia, Conteudo, Sessao, engine
from services.telegram import send_message
from services.scraper import extrair_texto_da_url
from services.ai_assistant import pedir_ia

# Configuração de Logs Profissional
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Otimização de Performance do Banco (Modo WAL)
with engine.connect() as conn:
    conn.execute(sqlalchemy_text("PRAGMA journal_mode=WAL;"))

# --- CAMADA DE SERVIÇOS EM BACKGROUND ---

def task_processor(chat_id, user_id, sessao_id, action_type, payload=None):
    """
    Worker independente: Gerencia seu próprio ciclo de vida e banco de dados.
    Isso evita vazamento de memória e deadlocks entre threads.
    """
    db = SessionLocal()
    try:
        sessao = db.query(Sessao).get(sessao_id)
        if not sessao: return

        if action_type == "/resumir":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            if materiais:
                send_message(chat_id, "🤖 *Gerando resumo analítico...*")
                corpo_texto = " ".join([c.texto for c in materiais])
                res = pedir_ia("Resumo executivo em tópicos curtos.", corpo_texto)
                send_message(chat_id, res)
            else:
                send_message(chat_id, "⚠️ Não há conteúdo salvo para esta matéria.")

        elif action_type == "/gerar_questoes":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            if materiais:
                send_message(chat_id, "🤖 *Preparando quiz...*")
                corpo_texto = " ".join([c.texto for c in materiais])
                prompt = (
                    "Crie 3 questões de múltipla escolha. No final, escreva 'GABARITO:' "
                    "e oculte as respostas com <tg-spoiler>RESPOSTA</tg-spoiler>."
                )
                res = pedir_ia(prompt, corpo_texto)
                send_message(chat_id, res)

        elif action_type == "auto_save":
            if payload.startswith("http"):
                send_message(chat_id, "🌐 *Processando link...*")
                texto = extrair_texto_da_url(payload)
                tipo = "link"
            else:
                texto, tipo = payload, "texto"
            
            if texto:
                db.add(Conteudo(texto=texto, tipo=tipo, materia_id=sessao.materia_ativa))
                db.commit()
                send_message(chat_id, "✅ Conteúdo indexado com sucesso.")

    except Exception as e:
        logger.error(f"Falha na Task [{action_type}]: {e}")
        send_message(chat_id, "❌ Erro ao processar sua solicitação.")
    finally:
        db.close()

# --- CONTROLADOR (WEBHOOK) ---

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Entrypoint: Valida a requisição e delega para o background.
    Garante resposta 200 OK imediata para evitar retentativas do Telegram.
    """
    db = SessionLocal()
    try:
        data = request.json
        msg = data.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text")

        if not chat_id or not text:
            return jsonify({"status": "ignored"}), 200

        # 1. Recuperação de Contexto (Rápido)
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

        # 2. Roteamento de Comandos
        if text in ["/start", "/menu"]:
            menu = (
                "📚 *ASSISTENTE DE ESTUDOS*\n\n"
                "/add [nome] - Nova matéria\n"
                "/materias - Listar matérias\n"
                "/use [nome] - Selecionar foco\n"
                "/status - Matéria ativa\n\n"
                "🤖 *IA*\n"
                "/resumir | /gerar_questoes"
            )
            send_message(chat_id, menu)

        elif text == "/status":
            m = db.query(Materia).get(sessao.materia_ativa) if sessao.materia_ativa else None
            send_message(chat_id, f"📖 *Foco atual:* {m.nome if m else 'Nenhum'}")

        elif text.startswith("/add"):
            nome = text.replace("/add", "").strip()
            if nome:
                db.add(Materia(nome=nome, user_id=user.id))
                db.commit()
                send_message(chat_id, f"✅ Matéria '{nome}' registrada.")

        elif text == "/materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()
            if mats:
                lista = "\n".join([f"{i+1}. {m.nome}" for i, m in enumerate(mats)])
                send_message(chat_id, f"📋 *Suas Matérias:*\n\n{lista}")
            else:
                send_message(chat_id, "📭 Nenhuma matéria criada.")

        elif text.startswith("/use"):
            nome = text.replace("/use", "").strip()
            m = db.query(Materia).filter_by(user_id=user.id, nome=nome).first()
            if m:
                sessao.materia_ativa = m.id
                db.commit()
                send_message(chat_id, f"🎯 Agora estudando: *{m.nome}*")
            else:
                send_message(chat_id, "⚠️ Matéria não encontrada.")

        # 3. Delegação de Tarefas Pesadas (Threads)
        elif text in ["/resumir", "/gerar_questoes"]:
            if sessao.materia_ativa:
                threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, text)).start()
            else:
                send_message(chat_id, "⚠️ Selecione uma matéria com /use antes.")

        elif not text.startswith("/"):
            if sessao.materia_ativa:
                threading.Thread(target=task_processor, args=(chat_id, user.id, sessao.id, "auto_save", text)).start()
            else:
                send_message(chat_id, "⚠️ Use /use [materia] para salvar conteúdo.")

    except Exception as e:
        logger.error(f"Erro no Webhook: {e}")
    finally:
        db.close()

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)