import random
import logging
from models import SessionLocal, Conteudo, Sessao
from services.telegram import send_message
from services.scraper import extrair_texto_da_url
from services.ai_assistant import pedir_ia
from services.chunker import chunk_text # Certifique-se de que o chunker está importado

logger = logging.getLogger(__name__)

def task_processor(chat_id, user_id, sessao_id, action_type, payload=None):
    """
    Processa as requisições pesadas em background.
    Usa amostragem inteligente e fatiamento de texto para economizar tokens e garantir velocidade.
    """
    db = SessionLocal()
    try:
        sessao = db.query(Sessao).get(sessao_id)

        if not sessao or not sessao.materia_ativa:
            send_message(chat_id, "⚠️ Nenhuma matéria ativa. Por favor, selecione uma no menu.")
            return

        # ==========================================
        # 1. GERAR RESUMO (Foco em Retenção Recente)
        # ==========================================
        if action_type == "/resumir":
            # Puxa apenas os 5 últimos blocos salvos (limitando o payload para a IA)
            materiais = db.query(Conteudo)\
                          .filter_by(materia_id=sessao.materia_ativa)\
                          .order_by(Conteudo.id.desc())\
                          .limit(5).all()
            
            if materiais:
                send_message(chat_id, "🤖 Lendo os últimos materiais e gerando um resumo...")
                
                # Reverte para manter a ordem cronológica do texto na leitura da IA
                materiais.reverse() 
                texto_compilado = "\n\n---\n\n".join([c.texto for c in materiais])
                
                prompt = "Com base no texto fornecido, crie um resumo direto ao ponto em 5 tópicos curtos. Use linguagem simples."
                res = pedir_ia(prompt, texto_compilado)
                send_message(chat_id, res)
            else:
                send_message(chat_id, "📭 A matéria está vazia. Envie textos ou links primeiro.")

        # ==========================================
        # 2. GERAR QUESTÕES (Revisão Dinâmica)
        # ==========================================
        elif action_type == "/gerar_questoes":
            # Puxa todos os blocos disponíveis da matéria
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            
            if materiais:
                send_message(chat_id, "🤖 Sorteando trechos da matéria para criar seu desafio...")
                
                # Amostragem aleatória: pega até 4 pedaços sortidos. 
                # Isso cria um efeito natural de flashcard/revisão espaçada.
                amostra = random.sample(materiais, min(len(materiais), 4))
                texto_compilado = "\n\n---\n\n".join([c.texto for c in amostra])
                
                prompt = (
                    "Use o conteúdo fornecido para criar 3 questões de múltipla escolha (A, B, C, D). "
                    "Faça perguntas que exijam raciocínio, não apenas decoreba. "
                    "Coloque o gabarito comentado no final."
                )
                res = pedir_ia(prompt, texto_compilado)
                send_message(chat_id, res)
            else:
                send_message(chat_id, "📭 A matéria está vazia. Envie textos ou links primeiro.")

        # ==========================================
        # 3. AUTO SAVE (Processamento e Chunking)
        # ==========================================
        elif action_type == "auto_save":
            if payload.startswith("http"):
                send_message(chat_id, "🌐 Extraindo texto do link...")
                texto_bruto = extrair_texto_da_url(payload)
                tipo = "link"
            else:
                texto_bruto = payload
                tipo = "texto"

            if texto_bruto:
                # Fatiamento estratégico: pedaços pequenos com overlap para não perder contexto
                pedacos = chunk_text(texto_bruto, max_chars=1000, overlap=100)
                
                for pedaco in pedacos:
                    novo_conteudo = Conteudo(
                        texto=pedaco, 
                        tipo=tipo, 
                        materia_id=sessao.materia_ativa
                    )
                    db.add(novo_conteudo)
                
                db.commit()
                send_message(chat_id, f"✅ Material processado com sucesso! Dividido em {len(pedacos)} blocos de conhecimento.")
            else:
                send_message(chat_id, "⚠️ Não consegui extrair informações úteis desse envio.")

        elif action_type == "/pergunta":
            materiais = db.query(Conteudo).filter_by(materia_id=sessao.materia_ativa).all()
            
            if materiais:
                send_message(chat_id, "🔍 Vasculhando seus materiais salvos para encontrar a resposta...")
                
                # Pega os últimos conteúdos salvos
                texto_compilado = "\n\n---\n\n".join([c.texto for c in materiais[-5:]])
                
                # Instrução separada do texto, exatamente como a função pedir_ia espera
                prompt = (
                    f"Você é um tutor de estudos amigável. O usuário fez a seguinte pergunta: '{payload}'\n\n"
                    f"Instruções:\n"
                    f"1. Responda APENAS E ESTRITAMENTE com base no texto fornecido.\n"
                    f"2. Se a resposta para a pergunta NÃO ESTIVER no texto, ou se for um assunto totalmente desconexo, "
                    f"você está PROIBIDO de inventar. Responda EXATAMENTE com esta frase:\n"
                    f"'Não tenho dados sobre esse assunto, mas caso você queira saber mais, pode me mandar links ou textos que eu criarei questões para ajudar.'\n"
                    f"3. Caso a resposta esteja no texto, seja direto e use linguagem simples."
                )
                
                # CORREÇÃO AQUI: Passando o prompt e o texto_compilado separadamente
                res = pedir_ia(prompt, texto_compilado)
                send_message(chat_id, res)
            else:
                send_message(chat_id, "📭 A matéria está vazia. Envie textos ou links primeiro.")

    except Exception as e:
        logger.error(f"Erro no processamento da task: {e}")
        send_message(chat_id, "❌ Ocorreu um erro interno. Tente novamente.")
    finally:
        db.close()