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


def higienizar_texto(texto: str) -> str:
    """Corrige erros de encoding (latin-1/utf-8) e limpa espaços excessivos."""
    if not texto:
        return ""
    try:
        texto = texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass  # Texto já está em UTF-8 ou não é conversível; segue em frente
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _salvar_pedacos(db, pedacos: list[str], tipo: str, materia_id: int) -> None:
    """Persiste os chunks no banco dentro de uma sessão já aberta."""
    for p in pedacos:
        db.add(Conteudo(texto=p, tipo=tipo, materia_id=materia_id))
    db.commit()


@telemetria
def processar_pdf(chat_id: int, materia_id: int, filepath: str) -> None:
    db = SessionLocal()
    try:
        send_message(chat_id, "📄 Lendo e fatiando seu PDF para o banco de dados...")
        texto = higienizar_texto(extrair_texto_pdf(filepath))

        if not texto or len(texto) < 10:
            send_message(chat_id, "❌ Não consegui extrair texto legível deste PDF.")
            return

        metricas.kb += len(texto.encode("utf-8")) / 1024
        pedacos = chunk_text(texto, max_chars=1000, overlap=100)
        _salvar_pedacos(db, pedacos, "pdf", materia_id)
        send_message(chat_id, f"✅ PDF absorvido! {len(pedacos)} blocos de conhecimento adicionados.")

    except Exception as e:
        logger.error(f"Erro ao processar PDF (chat={chat_id}): {e}", exc_info=True)
        send_message(chat_id, "❌ Ocorreu um erro interno ao processar o PDF.")
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
        db.close()


@telemetria
def processar_imagem(chat_id: int, materia_id: int, filepath: str) -> None:
    db = SessionLocal()
    try:
        send_message(chat_id, "🖼️ Extraindo texto da imagem...")
        texto = higienizar_texto(extrair_texto_imagem(filepath))

        if not texto:
            send_message(chat_id, "❌ Não encontrei nenhum texto nesta imagem.")
            return

        metricas.kb += len(texto.encode("utf-8")) / 1024
        pedacos = chunk_text(texto, max_chars=1000, overlap=100)
        _salvar_pedacos(db, pedacos, "imagem", materia_id)
        send_message(chat_id, f"✅ Imagem processada! {len(pedacos)} blocos adicionados.")

    except Exception as e:
        logger.error(f"Erro ao processar imagem (chat={chat_id}): {e}", exc_info=True)
        send_message(chat_id, "❌ Ocorreu um erro interno ao processar a imagem.")
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
        db.close()


@telemetria
def salvar_conteudo(chat_id: int, materia_id: int, payload: str) -> None:
    db = SessionLocal()
    try:
        tipo = "link" if payload.startswith(("http://", "https://")) else "texto"

        if tipo == "link":
            send_message(chat_id, "🔗 Acessando o link para leitura...")
            texto_bruto = extrair_texto_da_url(payload)
            if not texto_bruto or len(texto_bruto.strip()) < 10:
                send_message(
                    chat_id,
                    "⚠️ Este site bloqueia leitores. Por favor, cole o texto manualmente.",
                )
                return
        else:
            texto_bruto = payload

        texto = higienizar_texto(texto_bruto)
        if not texto:
            return

        metricas.kb += len(texto.encode("utf-8")) / 1024
        pedacos = chunk_text(texto, max_chars=1000, overlap=100)
        _salvar_pedacos(db, pedacos, tipo, materia_id)
        send_message(chat_id, f"✅ Absorvido! ({len(pedacos)} blocos arquivados na matéria)")

    except Exception as e:
        logger.error(f"Erro ao salvar conteúdo (chat={chat_id}): {e}", exc_info=True)
    finally:
        db.close()