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
            send_message(chat_id, "📭 Sua matéria está vazia.")
            return

        materiais = db.query(Conteudo).filter_by(materia_id=materia_id).order_by(Conteudo.id.desc()).limit(limite_por_pagina).offset(offset).all()

        if not materiais:
            send_message(chat_id, "✅ Conteúdo concluído!")
            return

        send_message(chat_id, f"📖 Lendo a parte {pagina}...")

        texto_base = "\n\n".join([c.texto for c in reversed(materiais)])
        tem_mais_conteudo = (offset + limite_por_pagina) < total_materiais

        # --- PROMPT REFORÇADO COM FOCO EM NEGRETOS (LEITURA BIÔNICA) ---
        prompt = (
            "Aja como um professor didático. Resuma o texto em tópicos seguindo EXATAMENTE este modelo:\n\n"
            "Número. <b>NOME DO TÓPICO</b>\n"
            "Explicação: Use <b>negrito</b> em TODAS as palavras-chave e conceitos centrais para facilitar a <b>leitura biônica</b>. "
            "A explicação deve ser uma síntese inteligente, não uma cópia.\n"
            "💡 <b>Exemplo prático:</b> [Analogia criativa e simples]\n\n"
            "REGRAS CRÍTICAS:\n"
            "- Use APENAS as tags HTML <b> e </b>.\n"
            "- Se você não usar negritos nas palavras-chave, o aluno não conseguirá aprender.\n"
        )
        
        if tem_mais_conteudo:
            prompt += (
                "\n\n🧠 Desafio Relâmpago de Retenção:\n"
                "Crie UMA ÚNICA pergunta de múltipla escolha.\n\n"
                "Formato OBRIGATÓRIO:\n"
                "Pergunta: [enunciado]\n"
                "A) [alternativa]\n"
                "B) [alternativa]\n\n"
                "REGRAS:\n"
                "- Deve existir apenas UMA pergunta\n"
                "- A e B são alternativas, NÃO perguntas\n"
                "- NÃO revele a resposta\n"
                "- Última linha: [GABARITO: A]"
            )
        
        res_raw, tokens = pedir_ia(prompt, texto_base)
        metricas.tokens += tokens
        
        # Restaura as tags e limpa o texto
        res = limpar_texto(res_raw).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")

        # 🎯 CAPTURA E LIMPEZA TOTAL DO GABARITO (Regex mais agressiva)
        gabarito = "A"

        # Captura o gabarito oficial
        match = re.search(r"\[GABARITO:\s*([A-B])\]", res, re.IGNORECASE)
        if match:
            gabarito = match.group(1).upper()

        # 🔥 REMOVE QUALQUER TIPO DE GABARITO (linha inteira)
        res = re.sub(r"\[GABARITO:.*?\]", "", res, flags=re.IGNORECASE)

        # 🔥 REMOVE FRASES QUE ENTREGAM A RESPOSTA
        res = re.sub(
            r"(resposta correta é|alternativa correta é|opção correta é|gabarito:|resposta:).*?(\n|$)",
            "",
            res,
            flags=re.IGNORECASE
        )

        # 🔥 REMOVE MARCAÇÕES TIPO (A) ou (B) no final
        res = re.sub(r"\([A-B]\)", "", res)

        # 🔥 REMOVE SOBRAS
        res = re.sub(r"\n{3,}", "\n\n", res).strip()

        # Gatilho de Áudio
        threading.Thread(target=pre_gerar_audio_resumo, args=(chat_id, res)).start()
        
        botoes = [[{"text": "🔊 Ouvir este resumo", "callback_data": "/audio_resumo"}]]

        if tem_mais_conteudo:
            res += "\n\n⚠️ <b>Escolha a opção correta para continuar:</b>"
            botoes.append([
                {"text": "🅰️ Opção A", "callback_data": f"/chk_{materia_id}_{pagina + 1}_A_{gabarito}"},
                {"text": "🅱️ Opção B", "callback_data": f"/chk_{materia_id}_{pagina + 1}_B_{gabarito}"}
            ])

        send_message(chat_id, res, {"inline_keyboard": botoes})
        
    except Exception as e:
        logger.error(f"Erro: {e}")
        send_message(chat_id, "⚠️ Erro ao processar. Tente novamente.")
    finally:
        db.close()

def processar_resposta_desafio(chat_id, materia_id, proxima_pagina, escolha, gabarito):
    """
    Avalia a resposta do quiz e prossegue para a próxima página.
    """
    if escolha == gabarito:
        feedback = random.choice(FEEDBACKS_ACERTO)
        msg_completa = f"✨ <b>{feedback}</b>\n\nCarregando próximo bloco..."
    else:
        feedback = random.choice(FEEDBACKS_ERRO)
        msg_completa = f"💡 <b>Nota de Apoio:</b> {feedback}\n\nVamos para a próxima parte:"
        
    send_message(chat_id, msg_completa)
    gerar_resumo(chat_id, materia_id, proxima_pagina)

# --- GESTÃO DE CONTEÚDO (Visual Estilizado) ---

def listar_conteudos(chat_id, user_id, materia_id):
    """Exibe a lista de materiais em formato de índice numerado."""
    db = SessionLocal()
    try:
        conteudos = db.query(Conteudo).filter_by(materia_id=materia_id).order_by(Conteudo.id.asc()).all()
        
        if not conteudos:
            send_message(chat_id, "📭 Nenhum conteúdo salvo nesta matéria ainda.")
            return

        botoes = []
        for i, c in enumerate(conteudos, 1):
            icone = "📄" if c.tipo == "pdf" else "🖼️" if c.tipo == "imagem" else "📝"
            # Preview curto para o botão
            preview = c.texto[:25].replace("\n", " ").strip() + "..."
            
            botoes.append([
                {"text": f"{icone} Bloco {i} | {preview}", "callback_data": f"/ver_conteudo {c.id}"}
            ])

        cabecalho = (
            "📚 <b>Base de Conhecimento</b>\n"
            "────────────────────\n"
            "<i>Aqui estão os materiais processados. Clique para ler:</i>"
        )
        
        send_message(chat_id, cabecalho, {"inline_keyboard": botoes})
    finally:
        db.close()

def ver_conteudo(chat_id, user_id, conteudo_id):
    """Exibe o texto completo de um bloco específico."""
    db = SessionLocal()
    try:
        c = db.query(Conteudo).get(conteudo_id)
        if not c:
            send_message(chat_id, "Conteúdo não encontrado.")
            return

        texto_limpo = limpar_texto(c.texto)
        
        # Visual de Card Profissional
        card = (
            f"📖 <b>Leitura de Material</b>\n"
            f"────────────────────\n\n"
            f"{texto_limpo}\n\n"
            f"────────────────────\n"
            f"📎 <b>Tipo:</b> {c.tipo.upper()}"
        )

        botoes = {
            "inline_keyboard": [
                [{"text": "🗑️ Excluir este Bloco", "callback_data": f"/confirm_del_ctd {c.id}"}],
                [{"text": "⬅️ Voltar à Lista", "callback_data": "/conteudos"}]
            ]
        }
        send_message(chat_id, card, botoes)
    finally:
        db.close()

def salvar_conteudo(chat_id, materia_id, payload):
    """
    Recebe texto ou link, extrai dados se necessário, 
    fatiando em chunks antes de salvar.
    """
    db = SessionLocal()
    try:
        tipo = "link" if payload.startswith("http") else "texto"
        
        if tipo == "link":
            send_message(chat_id, "🔗 Acessando o link para leitura...")
            texto = extrair_texto_da_url(payload)
            if not texto or len(texto.strip()) < 10:
                send_message(chat_id, "⚠️ Este site bloqueia leitores automáticos.")
                return
        else:
            texto = payload

        if texto:
            # Chunking para manter blocos processáveis pela IA
            pedacos = chunk_text(texto, max_chars=1000, overlap=100)
            for p in pedacos:
                db.add(Conteudo(texto=p, tipo=tipo, materia_id=materia_id))
            db.commit()
            send_message(chat_id, f"✅ Absorvido! ({len(pedacos)} blocos arquivados)")
    except Exception as e:
        logger.error(f"Erro ao salvar: {e}")
    finally:
        db.close()

def deletar_conteudo(chat_id, user_id, conteudo_id):
    """Remove um bloco de conteúdo do banco de dados."""
    db = SessionLocal()
    try:
        c = db.query(Conteudo).get(conteudo_id)
        if c:
            db.delete(c)
            db.commit()
            send_message(chat_id, "🗑️ Conteúdo excluído com sucesso!", {"inline_keyboard": [[{"text": "⬅️ Lista", "callback_data": "/conteudos"}]]})
    finally:
        db.close()

def confirmar_delete_conteudo(chat_id, conteudo_id):
    """Menu de confirmação para exclusão de material."""
    botoes = {
        "inline_keyboard": [
            [
                {"text": "✅ Sim, excluir", "callback_data": f"/delete_ctd {conteudo_id}"},
                {"text": "❌ Não, cancelar", "callback_data": "/conteudos"}
            ]
        ]
    }
    send_message(chat_id, "Tem certeza que deseja apagar este pedaço de material?", botoes)

# --- MÉTODOS DE INTELIGÊNCIA ARTIFICIAL (RAG) ---

@telemetria
def responder_pergunta(chat_id, materia_id, pergunta):
    """Busca contexto no banco e responde dúvida do aluno."""
    db = SessionLocal()
    try:
        materiais = db.query(Conteudo).filter_by(materia_id=materia_id).order_by(Conteudo.id.desc()).limit(10).all()
        if not materiais:
            send_message(chat_id, "📭 Sem material para consulta.")
            return

        contexto = "\n---\n".join([c.texto for c in materiais])
        prompt = (
            f"Use o CONTEXTO para responder a PERGUNTA do aluno amigavelmente.\n"
            f"Destaque termos fundamentais em HTML <b>.\n\nCONTEXTO:\n{contexto}"
        )
        
        res, tokens = pedir_ia(prompt, pergunta)
        metricas.tokens += tokens
        send_message(chat_id, f"<b>Resposta:</b>\n\n{limpar_texto(res)}")
    finally:
        db.close()

@telemetria
def gerar_questoes(chat_id, materia_id):
    """Cria um teste de múltipla escolha baseado no material salvo."""
    db = SessionLocal()
    try:
        materiais = db.query(Conteudo).filter_by(materia_id=materia_id).all()
        if not materiais: return
        
        amostra = random.sample(materiais, min(len(materiais), 4))
        texto_base = "\n\n".join([c.texto for c in amostra])
        
        prompt = "Crie 3 questões de múltipla escolha A-D. Use HTML <b>. Não coloque gabarito."
        res, tokens = pedir_ia(prompt, texto_base)
        metricas.tokens += tokens
        
        botoes = {
            "inline_keyboard": [
                [{"text": "🔊 Ouvir as Questões", "callback_data": "/audio_questoes"}],
                [{"text": "🔑 Ver Gabarito Comentado", "callback_data": "/ver_gabarito"}]
            ]
        }
        send_message(chat_id, limpar_texto(res), botoes)
    finally:
        db.close()

@telemetria
def gerar_gabarito_rag(chat_id, materia_id, texto_questoes):
    """Gera gabarito comentado buscando fontes no banco."""
    db = SessionLocal()
    try:
        materiais = db.query(Conteudo).filter_by(materia_id=materia_id).order_by(Conteudo.id.desc()).limit(10).all()
        contexto = "\n---\n".join([c.texto for c in materiais])
        
        prompt = f"Gere o gabarito oficial com base no CONTEXTO abaixo:\n\n{contexto}\n\nQUESTÕES:\n{texto_questoes}"
        res, tokens = pedir_ia(prompt, "")
        metricas.tokens += tokens
        send_message(chat_id, f"🎯 <b>Gabarito Oficial Comentado:</b>\n\n{limpar_texto(res)}")
    finally:
        db.close()