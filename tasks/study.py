import re
import random
import logging
import threading
from models import Materia, SessionLocal, Conteudo
from services.chunker import chunk_text
from services.scraper import extrair_texto_da_url
from services.telegram import send_message, send_voice
from services.ai_assistant import pedir_ia
from core.telemetry import telemetria, metricas
from utils.text_helpers import limpar_texto
from tasks.media import pre_gerar_audio_resumo

logger = logging.getLogger(__name__)

# --- BANCO DE FEEDBACKS METACOGNITIVOS (ACOLHIMENTO E APOIO) ---
FEEDBACKS_ERRO = [
    "Hum, esse conceito é meio escorregadio mesmo! Que tal dar uma repassada no áudio dessa parte depois? 🎧",
    "Quase lá! Essa parte tem alguns detalhes cheios de pegadinhas. Vale a pena ler o tópico acima com um pouquinho mais de calma. ⏱️",
    "Processar isso de primeira é um desafio real. Se sentir que a mente deu um nó, avance sem pressão e depois revisamos! 🧠",
    "Essa alternativa foi quase, mas o foco do texto era um pouquinho diferente. Que tal uma nova leitura rápida antes de prosseguir? 📖"
]

FEEDBACKS_ACERTO = [
    "Na mosca! Seu cérebro pescou o conceito central de primeira. Bora manter esse ritmo! 🚀",
    "Boa! Você pegou a lógica direto. Conexão neural feita com sucesso! 🧠⚡",
    "Perfeito! Retenção calibrada. Vamos ver o que vem a seguir? ⏭️",
    "Isso aí! Conhecimento consolidado. Você está dominando a matéria! 🏆"
]


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

        # Paginação nativa via banco: consome pouca memória e tokens por página
        materiais = db.query(Conteudo).filter_by(materia_id=materia_id).order_by(Conteudo.id.desc()).limit(limite_por_pagina).offset(offset).all()

        if not materiais:
            send_message(chat_id, "✅ Você já resumiu todo o conteúdo disponível desta matéria!")
            return

        msg_status = "💡 Montando um resumo da sua matéria, só um instante..." if pagina == 1 else f"📖 Lendo a parte {pagina}..."
        send_message(chat_id, msg_status)

        texto_base = "\n\n".join([c.texto for c in reversed(materiais)])
        
        tem_mais_conteudo = (offset + limite_por_pagina) < total_materiais

        # --- PROMPT DIDÁTICO E ACOLHEDOR (Equilíbrio de Tokens) ---
        # --- PROMPT DIDÁTICO E ACOLHEDOR (Equilíbrio de Tokens) ---
        prompt = (
            "Aja como um professor didático e acolhedor. Resuma o texto fornecido em tópicos de formato fixo:\n"
            "Número. <b>Nome do Tópico</b>\n"
            "Explicação simples do conceito com palavras-chave importantes em <b>negrito</b>.\n"
            "💡 <b>Exemplo prático:</b> [Exemplo real e lúdico do dia a dia]\n\n"
            "Use apenas HTML <b> e </b>, sem markdown ou asteriscos. Foque estritamente no texto enviado."
        )
        
        if tem_mais_conteudo:
            prompt += (
                "\n\nNo fim, adicione exatamente a seção:\n"
                "🧠 <b>Desafio Relâmpago de Retenção!</b>\n"
                "Faça uma pergunta rápida de múltipla escolha (apenas alternativas A e B) baseada no texto acima.\n"
                "REGRAS CRÍTICAS PARA O DESAFIO:\n"
                "1. NUNCA diga qual é a alternativa correta na pergunta ou nas opções.\n"
                "2. NUNCA use palavras como 'Correta', 'Errada', 'Verdadeira' ou 'Falsa' nas alternativas.\n"
            )
        
        resumo_raw, tokens = pedir_ia(prompt, texto_base)
        metricas.tokens += tokens
        
        if "Erro na IA" in resumo_raw:
            send_message(chat_id, "❌ Falha na conexão com a inteligência artificial. Pode tentar de novo em alguns instantes?")
            return

        # --- CORREÇÃO E RESTAURAÇÃO DO HTML DO TELEGRAM ---
        resumo_limpo = limpar_texto(resumo_raw)
        resumo_limpo = resumo_limpo.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;B&gt;", "<b>").replace("&lt;/B&gt;", "</b>")

        # 🎯 FILTRO ANTI-SPOILER (Novidade!)
        # Apaga frases como "A resposta correta é..." que a IA possa tentar incluir antes do gabarito oculto
        resumo_limpo = re.sub(r"(A resposta correta é|A alternativa correta é|A opção certa é).*?(\n|$)", "\n", resumo_limpo, flags=re.IGNORECASE)
        # Apaga indicadores diretos nas alternativas tipo "A) Opção X (Correta)"
        resumo_limpo = re.sub(r"\s*\(Correta\)", "", resumo_limpo, flags=re.IGNORECASE)

        # Extrai o gabarito oculto via Regex antes de enviar ao usuário
        gabarito = "A" # Fallback de segurança
        gabarito_match = re.search(r"\[GABARITO:\s*([A-B])\]", resumo_limpo, re.IGNORECASE)
        if gabarito_match:
            gabarito = gabarito_match.group(1).upper()
            # Remove o gabarito do texto visível
            resumo_limpo = re.sub(r"\[GABARITO:\s*[A-B]\]", "", resumo_limpo, flags=re.IGNORECASE).strip()

        # Proteção contra estouro de limite de texto do Telegram
        if len(resumo_limpo) > 4000:
            resumo_limpo = resumo_limpo[:3900]
            if resumo_limpo.count("<b>") > resumo_limpo.count("</b>"):
                resumo_limpo += "</b>"
            resumo_limpo += "...\n\n[⚠️ Resumo reduzido para não ultrapassar o limite do Telegram]"

        # --- GATILHO DO EAGER LOADING (AUDIO EM BACKGROUND THREAD) ---
        threading.Thread(target=pre_gerar_audio_resumo, args=(chat_id, resumo_limpo)).start()
        # --------------------------------------------------------------
        
        botoes = []
        botoes.append([{"text": "🔊 Ouvir este resumo", "callback_data": "/audio_resumo"}])

        if tem_mais_conteudo:
            aviso = "\n\n⚠️ <b>Responda ao desafio acima clicando na alternativa correta para testar sua fixação e liberar a próxima parte!</b>"
            resumo_limpo += aviso
            
            # Encoda o payload de 5 partes exigido pelo webhook do app.py
            botoes.append([
                {"text": "🅰️ Opção A", "callback_data": f"/chk_{materia_id}_{pagina + 1}_A_{gabarito}"},
                {"text": "🅱️ Opção B", "callback_data": f"/chk_{materia_id}_{pagina + 1}_B_{gabarito}"}
            ])
        else:
            resumo_limpo += "\n\n🎉 <b>Parabéns! Você completou todos os materiais dessa matéria!</b> Pronto para a próxima jornada? 🚀"

        teclado_opcoes = {"inline_keyboard": botoes}
        send_message(chat_id, resumo_limpo, teclado_opcoes)
        
    except Exception as e:
        logger.error(f"Erro Resumo: {e}")
        send_message(chat_id, "⚠️ Tive uma pequena oscilação ao estruturar essa parte. Poderia tentar novamente?")
    finally:
        db.close()


# 🎯 SEM DECORATOR AQUI: Remove o aninhamento que duplicava a telemetria falsamente no terminal
def processar_resposta_desafio(chat_id, materia_id, proxima_pagina, escolha, gabarito):
    """Intercepta o clique do quiz, manda o feedback amigável e puxa a próxima página do resumo."""
    if escolha == gabarito:
        feedback = random.choice(FEEDBACKS_ACERTO)
        msg_completa = f"✨ <b>{feedback}</b>\n\nCarregando o próximo bloco de estudos..."
    else:
        feedback = random.choice(FEEDBACKS_ERRO)
        msg_completa = f"💡 <b>Nota de Apoio:</b> {feedback}\n\nMesmo assim, o aprendizado não para! Vamos para a próxima parte:"
        
    send_message(chat_id, msg_completa)
    
    # Chama recursivamente a próxima página de forma limpa
    gerar_resumo(chat_id, materia_id, proxima_pagina)


# --- MÉTODOS DE SUPORTE (RAG, QUESTÕES E GABARITOS) ---
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
            f"Use o CONTEXTO abaixo para responder a PERGUNTA do aluno.\n"
            f"Responda de forma simples, direta e amigável. Use tags HTML <b> e </b> "
            f"para destacar termos fundamentais. Não use markdown.\n\n"
            f"CONTEXTO:\n{contexto}"
        )
        
        res, tokens = pedir_ia(prompt, pergunta)
        metricas.tokens += tokens
        
        resposta_limpa = limpar_texto(res).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;B&gt;", "<b>").replace("&lt;/B&gt;", "</b>")
        send_message(chat_id, f"<b>Resposta:</b>\n\n{resposta_limpa}")
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
            "Com base no texto fornecido, crie 3 questões de múltipla escolha (A-D).\n"
            "Use as tags HTML <b> e </b> nos enunciados ou conceitos chave. Não use markdown.\n"
            "NÃO coloque a resposta correta e NÃO coloque o gabarito no texto."
        )
        
        questoes_raw, tokens = pedir_ia(prompt, texto_base)
        metricas.tokens += tokens
        
        questoes_limpas = limpar_texto(questoes_raw).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;B&gt;", "<b>").replace("&lt;/B&gt;", "</b>")

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
            f"Com base no CONTEXTO abaixo, resolva as QUESTÕES fornecidas e apresente o gabarito oficial.\n"
            f"Destaque as alternativas corretas usando tags HTML <b> e </b> e inclua uma breve explicação do porquê ela está correta. Não use markdown.\n\n"
            f"CONTEXTO:\n{contexto}\n\n"
            f"QUESTÕES:\n{texto_das_questoes}"
        )
        
        gabarito, tokens = pedir_ia(prompt, "")
        metricas.tokens += tokens
        
        gabarito_limpo = limpar_texto(gabarito).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;B&gt;", "<b>").replace("&lt;/B&gt;", "</b>")
        send_message(chat_id, f"🎯 <b>Gabarito Oficial Comentado:</b>\n\n{gabarito_limpo}")
    except Exception as e:
        logger.error(f"Erro Gabarito: {e}")
    finally:
        db.close()

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
            pedacos = chunk_text(texto, max_chars=1000, overlap=100)
            for p in pedacos:
                db.add(Conteudo(texto=p, tipo=tipo, materia_id=materia_id))
            db.commit()
            send_message(chat_id, f"✅ Absorvido! ({len(pedacos)} blocos arquivados na matéria)")
    finally:
        db.close()
        
def listar_conteudos(chat_id, user_id, materia_id):
    db = SessionLocal()
    try:
        conteudos = db.query(Conteudo).filter_by(
            materia_id=materia_id
        ).order_by(Conteudo.id.desc()).limit(20).all()

        if not conteudos:
            send_message(chat_id, "📭 Nenhum conteúdo salvo ainda.")
            return

        botoes = []

        for c in conteudos:
            preview = c.texto[:40].replace("\n", " ")
            if len(c.texto) > 40:
                preview += "..."

            botoes.append([
                {"text": preview, "callback_data": f"/ver_conteudo {c.id}"},
                {"text": "🗑️", "callback_data": f"/confirm_del_ctd {c.id}"}
            ])

        send_message(chat_id, "📄 Seus conteúdos:", {
            "inline_keyboard": botoes
        })

    finally:
        db.close()
        
def ver_conteudo(chat_id, user_id, conteudo_id):
    db = SessionLocal()
    try:
        c = db.query(Conteudo).get(conteudo_id)

        if not c:
            send_message(chat_id, "Conteúdo não encontrado.")
            return

        texto = limpar_texto(c.texto)

        if len(texto) > 4000:
            texto = texto[:3900] + "\n\n[⚠️ Conteúdo cortado]"

        botoes = {
            "inline_keyboard": [
                [{"text": "🗑️ Excluir", "callback_data": f"/confirm_del_ctd {c.id}"}]
            ]
        }

        send_message(chat_id, f"📄 Conteúdo:\n\n{texto}", botoes)

    finally:
        db.close()
        
def deletar_conteudo(chat_id, user_id, conteudo_id):
    db = SessionLocal()
    try:
        c = db.query(Conteudo).join(Materia).filter(
            Conteudo.id == conteudo_id,
            Materia.user_id == user_id
        ).first()

        if not c:
            send_message(chat_id, "Conteúdo não encontrado ou não pertence a você.")
            return

        db.delete(c)
        db.commit()

        send_message(chat_id, "🗑️ Conteúdo excluído com sucesso!")

    finally:
        db.close()
        
def confirmar_delete_conteudo(chat_id, conteudo_id):
    botoes = {
        "inline_keyboard": [
            [
                {"text": "✅ Sim", "callback_data": f"/delete_ctd {conteudo_id}"},
                {"text": "❌ Cancelar", "callback_data": "/conteudos"}
            ]
        ]
    }

    send_message(chat_id, "Tem certeza que deseja excluir este conteúdo?", botoes)
