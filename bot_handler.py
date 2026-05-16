import threading
import logging
import requests
import os
from models import SessionLocal, User, Materia, Sessao
from services.telegram import send_message
from config import BASE_URL
from tasks import (
    gerar_resumo, gerar_questoes, salvar_conteudo, 
    responder_pergunta, processar_pdf, task_gerar_audio, gerar_gabarito_rag
)

logger = logging.getLogger(__name__)

def processar_mensagem(msg):
    chat_id = msg["chat"]["id"]
    texto = msg.get("text", "")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=str(chat_id)).first()
        if not user:
            user = User(telegram_id=str(chat_id))
            db.add(user); db.commit(); db.refresh(user)

        sessao = db.query(Sessao).filter_by(user_id=user.id).first()
        if not sessao:
            sessao = Sessao(user_id=user.id)
            db.add(sessao); db.commit(); db.refresh(sessao)

        materia_nome = "Nenhuma"
        if sessao.materia_ativa:
            m_ativa = db.query(Materia).get(sessao.materia_ativa)
            if m_ativa:
                materia_nome = m_ativa.nome

        menu_bolhas = {
            "inline_keyboard": [
                [{"text": "📊 Resumir", "callback_data": "/resumir"}, {"text": "📝 Questoes", "callback_data": "/gerar_questoes"}],
                [{"text": "📚 Minhas Materias", "callback_data": "/materias"}, {"text": "➕ Nova Materia", "callback_data": "/nova_materia"}],
                [{"text": "💡 Ajuda", "callback_data": "/ajuda"}]
            ]
        }

        if texto in ["/ajuda", "/start"]:
            ajuda_estilizada = (
                "<b>💡 O SEGREDO DO FUNCIONAMENTO</b>\n\n"
                "Eu sou um <b>assistente de organização</b>, não um criador de conteúdo. "
                "<u>Não consigo fazer nada sem que você envie a matéria primeiro.</u> "
                "Eu não invento informações; eu processo o que você me manda para facilitar seu estudo.\n\n"
                "<b>❓ COMO FALAR COMIGO?</b>\n"
                "• <b>Perguntas:</b> Termine qualquer frase com <b>'?'</b>. Eu vou vasculhar seus textos salvos.\n"
                "• <b>Comandos:</b> Qualquer mensagem que comece com <code>/</code>.\n"
                "• <b>Conteúdo:</b> Tudo o que digitar (que não termine com '?' e sem /) será <b>salvo automaticamente</b>.\n\n"
                "<b>🚀 PASSO A PASSO RÁPIDO</b>\n"
                "1. Use <code>/add Nome</code> para criar a disciplina.\n"
                "2. Em <b>Minhas Matérias</b>, selecione a que deseja alimentar.\n"
                "3. Mande textos, links ou PDFs.\n"
                "4. Use o <b>/menu</b> para gerar resumos e testes."
            )
            send_message(chat_id, ajuda_estilizada, menu_bolhas)
            return

        elif texto == "/menu":
            send_message(chat_id, f"Materia Selecionada: {materia_nome}\n\nEscolha uma opcao:", menu_bolhas)
            return

        elif texto == "/nova_materia":
            send_message(chat_id, "Para criar uma nova materia, digite:\n\n/add NomeDaMateria")
            return

        # INTERCEPTA O AUDIO DO RESUMO
        elif texto == "/audio_resumo":
            texto_para_ouvir = msg.get("conteudo_da_bolha", "")
            threading.Thread(target=task_gerar_audio, args=(chat_id, user.id, texto_para_ouvir)).start()
            return

        # INTERCEPTA O AUDIO DAS QUESTÕES
        elif texto == "/audio_questoes":
            texto_das_questoes = msg.get("conteudo_da_bolha", "")
            threading.Thread(target=task_gerar_audio, args=(chat_id, user.id, texto_das_questoes)).start()
            return

        # INTERCEPTA O CLIQUE PARA EXIBIR GABARITO
        elif texto == "/ver_gabarito":
            texto_das_questoes = msg.get("conteudo_da_bolha", "")
            threading.Thread(target=gerar_gabarito_rag, args=(chat_id, sessao.materia_ativa, texto_das_questoes)).start()
            return

        elif texto == "/materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()
            if mats:
                botoes = {"inline_keyboard": [[{"text": m.nome, "callback_data": f"/use {m.nome}"}] for m in mats]}
                send_message(chat_id, "Suas materias salvas:", botoes)
            else:
                send_message(chat_id, "Voce ainda nao tem materias. Use /add NomeDaMateria")
            return

        elif texto.startswith("/add "):
            nome = texto.replace("/add ", "").strip()
            db.add(Materia(nome=nome, user_id=user.id)); db.commit()
            send_message(chat_id, f"Materia {nome} criada! Selecione em /materias", menu_bolhas)
            return

        elif texto.startswith("/use "):
            nome = texto.replace("/use ", "").strip()
            m = db.query(Materia).filter_by(user_id=user.id, nome=nome).first()
            if m:
                sessao.materia_ativa = m.id; db.commit()
                send_message(chat_id, f"Materia Ativa: {m.nome}\n\nO que vamos estudar agora?", menu_bolhas)
            else:
                send_message(chat_id, "Materia nao encontrada.")
            return

        if not sessao.materia_ativa:
            send_message(chat_id, "⚠️ Selecione uma materia primeiro em /materias", menu_bolhas)
            return

        if "document" in msg:
            doc = msg["document"]
            if doc.get("mime_type") == "application/pdf":
                file_id = doc["file_id"]
                file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
                file_path = file_info["result"]["file_path"]
                token = BASE_URL.split('bot')[1]
                file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                
                local_path = f"temp_{file_id}.pdf"
                with open(local_path, "wb") as f:
                    f.write(requests.get(file_url).content)
                
                threading.Thread(target=processar_pdf, args=(chat_id, sessao.materia_ativa, local_path)).start()
                return
            else:
                send_message(chat_id, "❌ No momento so consigo ler arquivos PDF.")
                return

        # --- ROTAS DE IA ---
        if texto == "/resumir":
            # Começa o resumo sempre pela página 1 (os conteúdos mais recentes)
            threading.Thread(target=gerar_resumo, args=(chat_id, sessao.materia_ativa, 1)).start()
            return
            
        elif texto.startswith("/resumir_pag_"):
            # Identifica qual página de resumo o usuário pediu
            try:
                pagina = int(texto.split("_")[2])
                threading.Thread(target=gerar_resumo, args=(chat_id, sessao.materia_ativa, pagina)).start()
            except Exception:
                pass
            return
        
        elif texto == "/gerar_questoes":
            threading.Thread(target=gerar_questoes, args=(chat_id, sessao.materia_ativa)).start()
            
        elif texto.strip().endswith("?"):
            threading.Thread(target=responder_pergunta, args=(chat_id, sessao.materia_ativa, texto)).start()
            
        elif texto and not texto.startswith("/"):
            threading.Thread(target=salvar_conteudo, args=(chat_id, sessao.materia_ativa, texto)).start()

    except Exception as e:
        logger.error(f"Erro no bot_handler: {e}")
        send_message(chat_id, "Ocorreu um erro ao processar sua solicitação.")
    finally:
        db.close()