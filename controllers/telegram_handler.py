import threading
import logging
import requests
import os
from models import SessionLocal, Materia
from services.telegram import send_message
from config import BASE_URL
from tasks.ingestion import processar_pdf, salvar_conteudo
from tasks.study import gerar_resumo, gerar_questoes, responder_pergunta, gerar_gabarito_rag
from tasks.media import task_gerar_audio
from core.auth import obter_sessao_usuario
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

        elif texto == "/nova_materia":
            send_message_async(chat_id, "Para criar uma nova materia, digite:\n\n/add NomeDaMateria")
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

        # 4. Gerenciamento de Matérias
        elif texto == "/materias":
            mats = db.query(Materia).filter_by(user_id=user.id).all()
            if mats:
                botoes = {"inline_keyboard": [[{"text": m.nome, "callback_data": f"/use {m.nome}"}] for m in mats]}
                send_message_async(chat_id, "Suas materias salvas:", botoes)
            else:
                send_message_async(chat_id, "Voce ainda nao tem materias. Use /add NomeDaMateria")
            return

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

        # 6. Rotas de Estudo (IA e Ingestão de Texto)
        if texto == "/resumir":
            send_message_async(chat_id, "⏳ Montando um resumo da sua matéria, só um instante...")
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