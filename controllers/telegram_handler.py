import threading
import logging
import requests
import os
from models import SessionLocal, Materia
from services.telegram import send_message
from config import BASE_URL
from tasks.ingestion import processar_imagem, processar_pdf, salvar_conteudo
from tasks.study import confirmar_delete_conteudo, deletar_conteudo, gerar_resumo, gerar_questoes, listar_conteudos, responder_pergunta, gerar_gabarito_rag, ver_conteudo
from core.auth import obter_sessao_usuario
from tasks.media import task_gerar_audio
from utils.menus import MENU_PRINCIPAL, TEXTO_AJUDA

logger = logging.getLogger(__name__)

# Wrapper para envios rápidos que não bloqueiam a main thread
def send_message_async(chat_id, text, reply_markup=None):
    threading.Thread(target=send_message, args=(chat_id, text, reply_markup)).start()

def processar_mensagem(msg):
    chat_id = msg["chat"]["id"]
    texto = msg.get("text", "")
    
    db = SessionLocal()
    try:
        # 1. Autenticação e Sessão (Delegado para o módulo core)
        user, sessao, materia_nome = obter_sessao_usuario(db, chat_id)

        # 2. Comandos Básicos e Navegação
        if texto in ["/ajuda", "/start"]:
            send_message_async(chat_id, TEXTO_AJUDA, MENU_PRINCIPAL)
            return

        elif texto == "/menu":
            send_message_async(chat_id, f"Materia Selecionada: {materia_nome}\n\nEscolha uma opcao:", MENU_PRINCIPAL)
            return

        # 🧠 NOVO FLUXO: Ativa o estado de criação usando o Sentinela -1
        elif texto == "/nova_materia":
            sessao.editando_materia_id = -1
            db.commit()
            send_message_async(chat_id, "✏️ Digite qual o nome da Matéria:")
            return

        # 3. Mídia e Áudio (Callbacks das bolhas)
        elif texto in ["/audio_resumo", "/audio_questoes"]:
            aviso = "🎙️ Colocando as cordas vocais para aquecer..." if "resumo" in texto else "🎙️ Preparando o áudio das questões..."
            send_message_async(chat_id, aviso)
            conteudo = msg.get("conteudo_da_bolha", "")
            threading.Thread(target=task_gerar_audio, args=(chat_id, user.id, conteudo)).start()
            return

        elif texto == "/ver_gabarito":
            send_message_async(chat_id, "✅ Buscando o gabarito no material de estudo...")
            conteudo = msg.get("conteudo_da_bolha", "")
            threading.Thread(target=gerar_gabarito_rag, args=(chat_id, sessao.materia_ativa, conteudo)).start()
            return

        # Mantido apenas como fallback seguro por comando
        elif texto.startswith("/add "):
            nome = texto.replace("/add ", "").strip()
            db.add(Materia(nome=nome, user_id=user.id)); db.commit()
            send_message_async(chat_id, f"Materia {nome} criada! Selecione em /materias", MENU_PRINCIPAL)
            return

        elif texto.startswith("/use "):
            nome = texto.replace("/use ", "").strip()
            m = db.query(Materia).filter_by(user_id=user.id, nome=nome).first()
            if m:
                sessao.materia_ativa = m.id; db.commit()
                send_message_async(chat_id, f"Materia Ativa: {m.nome}\n\nO que vamos estudar agora?", MENU_PRINCIPAL)
            else:
                send_message_async(chat_id, "Materia nao encontrada.")
            return
        
        elif texto == "/conteudos":
            listar_conteudos(chat_id, user.id, sessao.materia_ativa)

        elif texto.startswith("/ver_conteudo "):
            ver_conteudo(chat_id, user.id, int(texto.split()[1]))

        elif texto.startswith("/confirm_del_ctd "):
            confirmar_delete_conteudo(chat_id, int(texto.split()[1]))

        elif texto.startswith("/delete_ctd "):
            deletar_conteudo(chat_id, user.id, int(texto.split()[1]))

        elif texto == "/materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()
            if mats:
                botoes_lista = []

                for m in mats:
                    botoes_lista.append([
                        {"text": m.nome, "callback_data": f"/use {m.nome}"}
                    ])
                    botoes_lista.append([
                        {"text": "✏️", "callback_data": f"/edit {m.id}"},
                        {"text": "🗑️", "callback_data": f"/confirm_delete {m.id}"}
                    ])

                botoes = {
                    "inline_keyboard": botoes_lista
                }
                send_message(chat_id, "Suas materias salvas:", botoes)
            else:
                send_message(
                    chat_id, "Voce ainda nao tem materias. Use /add NomeDaMateria"
                )
            return

        elif texto.startswith("/delete "):
            materia_id = int(texto.split(" ")[1])
            m = db.query(Materia).filter_by(user_id=user.id, id=materia_id).first()

            if m:
                if sessao.materia_ativa == m.id:
                    sessao.materia_ativa = None

                db.delete(m)
                db.commit()

                send_message(chat_id, "🗑️ Matéria excluída com sucesso!", MENU_PRINCIPAL)
            else:
                send_message(chat_id, "Matéria não encontrada.")
            return
        
        elif texto.startswith("/confirm_delete "):
            materia_id = int(texto.split(" ")[1])

            botoes = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Sim", "callback_data": f"/delete {materia_id}"},
                        {"text": "❌ Não", "callback_data": "/materias"}
                    ]
                ]
            }

            send_message(chat_id, "Tem certeza que deseja excluir esta matéria?", botoes)
            return
        
        elif texto.startswith("/edit "):
            materia_id = int(texto.split(" ")[1])
            sessao.editando_materia_id = materia_id
            db.commit()

            send_message(chat_id, "✏️ Digite o novo nome da matéria:")
            return

# 🧠 MÁQUINA DE ESTADOS: Captura o texto para Criação ou Edição
        elif sessao.editando_materia_id and not texto.startswith("/"):
            if sessao.editando_materia_id == -1:
                # Caso seja -1, significa que o usuário está CRIANDO uma nova matéria
                nome_materia = texto.strip()
                db.add(Materia(nome=nome_materia, user_id=user.id))
                sessao.editando_materia_id = None
                db.commit()
                # 🎯 CORRIGIDO: </b> com barra fechando a tag corretamente
                send_message_async(chat_id, f"✅ Matéria <b>{nome_materia}</b> criada com sucesso! Selecione em /materias", MENU_PRINCIPAL)
            else:
                # Caso contrário, está EDITANDO uma matéria existente
                m = db.query(Materia).filter_by(
                    user_id=user.id,
                    id=sessao.editando_materia_id
                ).first()

                if m:
                    m.nome = texto.strip()
                    sessao.editando_materia_id = None
                    db.commit()
                    send_message_async(chat_id, "✏️ Matéria atualizada com sucesso!", MENU_PRINCIPAL)
                else:
                    send_message_async(chat_id, "Erro ao editar matéria.")
            return 

        # --- BLOQUEIO DE SEGURANÇA ---
        if not sessao.materia_ativa:
            send_message_async(chat_id, "⚠️ Selecione uma materia primeiro em /materias", MENU_PRINCIPAL)
            return

        # 5. Recepção de Arquivos (PDF)
        if "document" in msg:
            doc = msg["document"]
            if doc.get("mime_type") == "application/pdf":
                send_message_async(chat_id, "📄 Recebi o PDF! Iniciando a leitura e extração dos dados...")
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
                send_message_async(chat_id, "❌ No momento so consigo ler arquivos PDF.")
                return
            
        # 6. Recepção de Imagens
        if "photo" in msg:
            send_message_async(chat_id, "🖼️ Recebi a imagem! Extraindo o texto...")

            photo = msg["photo"][-1]
            file_id = photo["file_id"]

            file_info = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()
            file_path = file_info["result"]["file_path"]

            token = BASE_URL.split('bot')[1]
            file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"

            local_path = f"temp_{file_id}.jpg"
            with open(local_path, "wb") as f:
                f.write(requests.get(file_url).content)

            threading.Thread(
                target=processar_imagem,
                args=(chat_id, sessao.materia_ativa, local_path)
            ).start()

            return

        # 7 Rotas de Estudo (IA e Ingestão de Texto)
        if texto == "/resumir":
            threading.Thread(target=gerar_resumo, args=(chat_id, sessao.materia_ativa, 1)).start()
            
        elif texto.startswith("/resumir_pag_"):
            send_message_async(chat_id, "⏳ Gerando a continuação do resumo...")
            try:
                pagina = int(texto.split("_")[2])
                threading.Thread(target=gerar_resumo, args=(chat_id, sessao.materia_ativa, pagina)).start()
            except Exception:
                pass
        
        elif texto == "/gerar_questoes":
            send_message_async(chat_id, "📝 Analisando seu material para bolar as questões, aguarde...")
            threading.Thread(target=gerar_questoes, args=(chat_id, sessao.materia_ativa)).start()
            
        elif texto.strip().endswith("?"):
            send_message_async(chat_id, "🔎 Consultando sua base de conhecimento para encontrar a resposta...")
            threading.Thread(target=responder_pergunta, args=(chat_id, sessao.materia_ativa, texto)).start()
            
        elif texto and not texto.startswith("/"):
            send_message_async(chat_id, "💾 Conteúdo recebido! Processando e fragmentando para a base de estudos...")
            threading.Thread(target=salvar_conteudo, args=(chat_id, sessao.materia_ativa, texto)).start()

    except Exception as e:
        logger.error(f"Erro no bot_handler: {e}")
        send_message_async(chat_id, "Ocorreu um erro ao processar sua solicitação.")
    finally:
        db.close()