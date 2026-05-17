import os
import re
import logging
from models import SessionLocal, Conteudo
from services.image_reader import extrair_texto_imagem
from services.telegram import send_message
from services.scraper import extrair_texto_da_url
from services.chunker import chunk_text
from services.pdf_reader import extrair_texto_pdf
from core.telemetry import telemetria, metricas

logger = logging.getLogger(__name__)

def higienizar_texto(texto):
    """Corrige erros de encoding (ÃSÃ£o) e limpa espaços excessivos."""
    if not texto: return ""
    try:
        # Tenta corrigir quebras de encoding comuns em PDFs
        texto = texto.encode('latin-1').decode('utf-8')
    except:
        pass
    # Remove excesso de espaços e quebras de linha para economizar tokens
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

@telemetria
def processar_pdf(chat_id, materia_id, filepath):
    db = SessionLocal()
    try:
        send_message(chat_id, "📄 Lendo e fatiando seu PDF para o banco de dados...")
        texto_bruto = extrair_texto_pdf(filepath)
        texto = higienizar_texto(texto_bruto)
        
        if not texto or len(texto) < 10:
            send_message(chat_id, "❌ Não consegui extrair texto legível deste PDF.")
            return

        metricas.kb += len(texto.encode('utf-8')) / 1024
        pedacos = chunk_text(texto, max_chars=1000, overlap=100)
        
        for p in pedacos:
            db.add(Conteudo(texto=p, tipo="pdf", materia_id=materia_id))
        db.commit()
        send_message(chat_id, f"✅ PDF absorvido! {len(pedacos)} blocos de conhecimento adicionados.")
    except Exception as e:
        logger.error(f"Erro PDF: {e}")
    finally:
        if os.path.exists(filepath): os.remove(filepath)
        db.close()
        
@telemetria
def processar_imagem(chat_id, materia_id, filepath):
    db = SessionLocal()
    try:
        send_message(chat_id, "🖼️ Extraindo texto da imagem...")
        texto_bruto = extrair_texto_imagem(filepath)
        texto = higienizar_texto(texto_bruto)

        if not texto.strip():
            send_message(chat_id, "❌ Não encontrei nenhum texto nesta imagem.")
            return

        metricas.kb += len(texto.encode('utf-8')) / 1024
        pedacos = chunk_text(texto, max_chars=1000, overlap=100)

        for p in pedacos:
            db.add(Conteudo(texto=p, tipo="imagem", materia_id=materia_id))
        db.commit()
        send_message(chat_id, f"✅ Imagem processada! {len(pedacos)} blocos adicionados.")

    except Exception as e:
        logger.error(f"Erro imagem: {e}")
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
            texto_bruto = extrair_texto_da_url(payload)
            if not texto_bruto or len(texto_bruto.strip()) < 10:
                send_message(chat_id, "⚠️ Este site bloqueia leitores. Por favor, cole o texto manualmente.")
                return
        else:
            texto_bruto = payload

        texto = higienizar_texto(texto_bruto)
        if texto:
            metricas.kb += len(texto.encode('utf-8')) / 1024
            pedacos = chunk_text(texto, max_chars=1000, overlap=100)
            for p in pedacos:
                db.add(Conteudo(texto=p, tipo=tipo, materia_id=materia_id))
            db.commit()
            send_message(chat_id, f"✅ Absorvido! ({len(pedacos)} blocos arquivados na matéria)")
    finally:
        db.close()