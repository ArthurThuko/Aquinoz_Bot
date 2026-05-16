import random
import logging
import threading
from models import SessionLocal, Conteudo
from services.telegram import send_message
from services.ai_assistant import pedir_ia
from core.telemetry import telemetria, metricas
from utils.text_helpers import limpar_texto
from tasks.media import pre_gerar_audio_resumo

logger = logging.getLogger(__name__)

@telemetria
def gerar_resumo(chat_id, materia_id, pagina=1):
    db = SessionLocal()
    try:
        limite_por_pagina = 3
        offset = (pagina - 1) * limite_por_pagina
        total_materiais = db.query(Conteudo).filter_by(materia_id=materia_id).count()

        if total_materiais == 0:
            send_message(chat_id, "📭 Sua matéria está vazia. Adicione links, textos e PDFs para começar sua jornada de estudos!")
            return

        materiais = db.query(Conteudo).filter_by(materia_id=materia_id).order_by(Conteudo.id.desc()).limit(limite_por_pagina).offset(offset).all()

        if not materiais:
            send_message(chat_id, "✅ Você já resumiu todo o conteúdo disponível desta matéria!")
            return

        msg_status = "Analisando seus materiais e preparando o resumo..." if pagina == 1 else f"Lendo a parte {pagina} dos seus materiais..."
        send_message(chat_id, msg_status)

        texto_base = "\n\n".join([c.texto for c in reversed(materiais)])
        
        prompt = (
            "Crie um resumo simples e COMPLETO do texto fornecido. "
            "NAO use negrito, asteriscos ou markdown. Use apenas texto puro. "
            "Siga rigorosamente este formato para cada tópico:\n"
            "Numero. Nome do Tópico\n"
            "Explicação simples.\n"
            "Exemplo prático: [exemplo aqui]\n\n"
            "IMPORTANTE: Vá direto ao ponto e conclua todas as frases perfeitamente."
        )
        
        resumo_raw, tokens = pedir_ia(prompt, texto_base)
        metricas.tokens += tokens
        
        if "Erro na IA" in resumo_raw:
            send_message(chat_id, "❌ Falha na conexão com a inteligência artificial. Pode tentar de novo em alguns instantes?")
            return

        resumo_limpo = limpar_texto(resumo_raw)

        if len(resumo_limpo) > 4000:
            resumo_limpo = resumo_limpo[:3900] + "...\n\n[⚠️ Resumo reduzido para não ultrapassar o limite do Telegram]"

        # --- GATILHO DO EAGER LOADING (ILUSÃO DE TRABALHO) ---
        # Dispara a geração da parte 1 em background sem travar a entrega do texto
        threading.Thread(target=pre_gerar_audio_resumo, args=(chat_id, resumo_limpo)).start()
        # -----------------------------------------------------

        tem_mais_conteudo = (offset + limite_por_pagina) < total_materiais
        
        botoes = []
        botoes.append([{"text": "🔊 Ouvir este resumo", "callback_data": "/audio_resumo"}])

        if tem_mais_conteudo:
            aviso = "\n\n⚠️ Existem mais conteúdos na matéria. Posso fazer o resumo da próxima parte?"
            resumo_limpo += aviso
            botoes.append([{"text": f"⏭️ Fazer Parte {pagina + 1}", "callback_data": f"/resumir_pag_{pagina + 1}"}])

        teclado_opcoes = {"inline_keyboard": botoes}
        
        send_message(chat_id, resumo_limpo, teclado_opcoes)
        
    except Exception as e:
        logger.error(f"Erro Resumo: {e}")
        send_message(chat_id, "⚠️ Tive uma pequena oscilação ao estruturar essa parte. Poderia tentar novamente?")
    finally:
        db.close()

@telemetria
def responder_pergunta(chat_id, materia_id, pergunta):
    db = SessionLocal()
    try:
        materiais = db.query(Conteudo).filter_by(materia_id=materia_id).order_by(Conteudo.id.desc()).limit(10).all()
        if not materiais:
            send_message(chat_id, "📭 Sua matéria está vazia. Adicione textos para eu poder responder.")
            return

        send_message(chat_id, "Consultando seus materiais salvos...")
        contexto = "\n---\n".join([c.texto for c in materiais])
        
        prompt = (
            f"Use o CONTEXTO abaixo para responder a PERGUNTA do aluno. "
            f"Responda de forma simples e direta, sem usar markdown.\n\n"
            f"CONTEXTO:\n{contexto}"
        )
        
        res, tokens = pedir_ia(prompt, pergunta)
        metricas.tokens += tokens
        
        resposta_limpa = limpar_texto(res)
        
        if len(resposta_limpa) > 4000:
            resposta_limpa = resposta_limpa[:3900] + "...\n\n[⚠️ Resposta muito longa cortada.]"
            
        send_message(chat_id, f"Resposta:\n\n{resposta_limpa}")
    except Exception as e:
        logger.error(f"Erro RAG: {e}")
    finally:
        db.close()

@telemetria
def gerar_questoes(chat_id, materia_id):
    db = SessionLocal()
    try:
        materiais = db.query(Conteudo).filter_by(materia_id=materia_id).all()
        if not materiais:
            send_message(chat_id, "📭 Não temos material suficiente aqui.")
            return

        send_message(chat_id, "Preparando seu teste de fixação...")
        amostra = random.sample(materiais, min(len(materiais), 4))
        texto_base = "\n\n".join([c.texto for c in amostra])
        
        prompt = (
            "Com base no texto fornecido, crie 3 questoes de multipla escolha (A-D). "
            "NAO coloque a resposta correta e NAO coloque o gabarito no texto. "
            "Use apenas texto puro, sem asteriscos ou markdown."
        )
        
        questoes_raw, tokens = pedir_ia(prompt, texto_base)
        metricas.tokens += tokens
        
        questoes_limpas = limpar_texto(questoes_raw)

        if len(questoes_limpas) > 4000:
            questoes_limpas = questoes_limpas[:3900] + "...\n\n[⚠️ Teste reduzido devido ao tamanho.]"

        botoes_questoes = {
            "inline_keyboard": [
                [{"text": "🔊 Ouvir as Questões", "callback_data": "/audio_questoes"}],
                [{"text": "🔑 Ver Gabarito Comentado", "callback_data": "/ver_gabarito"}]
            ]
        }
        
        send_message(chat_id, questoes_limpas, botoes_questoes)
    except Exception as e:
        logger.error(f"Erro Questoes: {e}")
    finally:
        db.close()

@telemetria
def gerar_gabarito_rag(chat_id, materia_id, texto_das_questoes):
    db = SessionLocal()
    try:
        send_message(chat_id, "🔑 Resolvendo as questões com base nos seus materiais...")
        
        materiais = db.query(Conteudo).filter_by(materia_id=materia_id).order_by(Conteudo.id.desc()).limit(10).all()
        contexto = "\n---\n".join([c.texto for c in materiais])
        
        prompt = (
            f"Com base no CONTEXTO abaixo, resolva as QUESTOES fornecidas e apresente o gabarito "
            f"com uma breve explicacao de por que cada alternativa e a correta. "
            f"Nao use markdown ou asteriscos.\n\n"
            f"CONTEXTO:\n{contexto}\n\n"
            f"QUESTOES:\n{texto_das_questoes}"
        )
        
        gabarito, tokens = pedir_ia(prompt, "")
        metricas.tokens += tokens
        
        gabarito_limpo = limpar_texto(gabarito)
        
        if len(gabarito_limpo) > 4000:
            gabarito_limpo = gabarito_limpo[:3900] + "...\n\n[⚠️ Gabarito reduzido devido ao tamanho.]"
            
        send_message(chat_id, f"🎯 Gabarito Oficial:\n\n{gabarito_limpo}")
    except Exception as e:
        logger.error(f"Erro Gabarito: {e}")
    finally:
        db.close()