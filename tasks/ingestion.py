import os
import logging
from models import SessionLocal, Conteudo
from services.telegram import send_message
from services.scraper import extrair_texto_da_url
from services.chunker import chunk_text
from services.pdf_reader import extrair_texto_pdf
from core.telemetry import telemetria, metricas

logger = logging.getLogger(__name__)

@telemetria
def processar_pdf(chat_id, materia_id, filepath):
    db = SessionLocal()
    try:
        send_message(chat_id, "Lendo e fatiando seu PDF para o banco de dados...")
        texto = extrair_texto_pdf(filepath)
        if not texto:
            send_message(chat_id, "Não consegui extrair o texto deste PDF.")
            return

        metricas.kb += len(texto.encode('utf-8')) / 1024

        pedacos = chunk_text(texto, max_chars=1000, overlap=100)
        for p in pedacos:
            db.add(Conteudo(texto=p, tipo="pdf", materia_id=materia_id))
        db.commit()
        send_message(chat_id, f"✅ PDF salvo! {len(pedacos)} blocos de conhecimento adicionados.")
    except Exception as e:
        logger.error(f"Erro PDF: {e}")
    finally:
        if os.path.exists(filepath): os.remove(filepath)
        db.close()

@telemetria
def salvar_conteudo(chat_id, materia_id, payload):
    db = SessionLocal()
    try:
        tipo = "link" if payload.startswith("http") else "texto"
        if tipo == "link":
            send_message(chat_id, "🔗 Acessando o link para leitura...")
            texto = extrair_texto_da_url(payload)
            if not texto or len(texto.strip()) < 10:
                send_message(chat_id, "⚠️ Este site bloqueia leitores automáticos. Por favor, copie e cole o texto no chat.")
                return
        else:
            texto = payload

        if texto:
            metricas.kb += len(texto.encode('utf-8')) / 1024
            
            pedacos = chunk_text(texto, max_chars=1000, overlap=100)
            for p in pedacos:
                db.add(Conteudo(texto=p, tipo=tipo, materia_id=materia_id))
            db.commit()
            send_message(chat_id, f"✅ Absorvido! ({len(pedacos)} blocos arquivados na matéria)")
    finally:
        db.close()