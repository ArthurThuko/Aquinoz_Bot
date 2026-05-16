import os
import re
import time
import logging
import threading
from services.telegram import send_message, send_voice
from services.voice import gerar_audio_do_texto
from core.telemetry import telemetria, metricas
from utils.text_helpers import dividir_texto_em_partes

logger = logging.getLogger(__name__)

def extrair_topicos(texto_fatiado):
    numeros = re.findall(r'^\s*(\d+)\.', texto_fatiado, re.MULTILINE)
    if not numeros:
        return " <i>(Continuação)</i>"
    num_ints = sorted([int(n) for n in numeros])
    min_topico, max_topico = num_ints[0], num_ints[-1]
    if min_topico == max_topico:
        return f" <b>(Tópico {min_topico})</b>"
    return f" <b>(Tópicos {min_topico}-{max_topico})</b>"

# --- LÓGICA DE PRE-GERAÇÃO (EAGER LOADING) ---
def autodestruir_arquivo(path, timeout=60):
    """Espera 60 segundos. Se o arquivo ainda existir (não foi ouvido), deleta."""
    time.sleep(timeout)
    if os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Lixeira: Arquivo {path} não utilizado apagado após {timeout}s.")
        except Exception: pass

def pre_gerar_audio_resumo(identificador, texto_completo):
    """Gera silenciosamente a Parte 1 do áudio em background."""
    try:
        partes = dividir_texto_em_partes(texto_completo)
        if partes:
            # Salva com o índice 'pre'
            path = gerar_audio_do_texto(partes[0], identificador, indice="pre")
            if path:
                # Inicia a contagem regressiva de destruição
                threading.Thread(target=autodestruir_arquivo, args=(path,)).start()
    except Exception as e:
        logger.error(f"Erro na pré-geração: {e}")
# ---------------------------------------------

@telemetria
def processar_parte_audio(chat_id, path, parte_atual, total_partes, topicos_str):
    try:
        if path:
            if total_partes > 1:
                msg_bonita = (
                    f"🎧 <b>Áudio {parte_atual} de {total_partes}</b>{topicos_str}\n"
                    f"<i>Pode dar o play! A próxima parte já está sendo preparada...</i> ⚡"
                )
                send_message(chat_id, msg_bonita)
            else:
                send_message(chat_id, f"🎧 <b>Seu áudio está pronto!</b>{topicos_str} Bom estudo. 🚀")
            
            if hasattr(metricas, 'kb'):
                metricas.kb += os.path.getsize(path) / 1024
                
            send_voice(chat_id, path)
            
            if os.path.exists(path): 
                os.remove(path)
        else:
            send_message(chat_id, f"⚠️ Tive um problema ao gerar a parte {parte_atual} do seu áudio.")
    except Exception as e:
        logger.error(f"Erro Áudio Parte {parte_atual}: {e}")

def task_gerar_audio(chat_id, user_id, texto):
    try:
        if not texto or "/audio_" in texto or "Analisando seus" in texto:
            return
            
        partes_texto = dividir_texto_em_partes(texto)
        total_partes = len(partes_texto)

        if total_partes > 1:
            send_message(chat_id, f"Sintetizando a voz... Fatiamos em <b>{total_partes} partes menores</b> para a primeira chegar super rápido! 🏃💨")
        else:
            send_message(chat_id, "🎙️ Colocando as cordas vocais para aquecer... gerando seu áudio!")

        resultados = {}
        # Caminho exato de onde o arquivo pre-gerado estaria salvo
        path_pre_gerado = f"temp_voice_{user_id}_parte_pre.mp3"
        
        def worker_geracao(texto_fatiado, indice):
            # Se for a Parte 1 e o arquivo do Eager Loading já existir no disco:
            if indice == 1 and os.path.exists(path_pre_gerado):
                # Labor Illusion: Segura 2 segundinhos para o usuário não assustar com a velocidade
                time.sleep(2)
                path = path_pre_gerado
            else:
                # Se não existir (passou 60s ou é a parte 2, 3...), gera normal na Microsoft
                path = gerar_audio_do_texto(texto_fatiado, user_id, indice=indice)
                
            topicos_str = extrair_topicos(texto_fatiado)
            resultados[indice] = {"path": path, "topicos_str": topicos_str}

        threads_geracao = []
        
        # Dispara a Thread 1
        t_primeira = threading.Thread(target=worker_geracao, args=(partes_texto[0], 1))
        t_primeira.start()
        threads_geracao.append(t_primeira)
        
        time.sleep(0.2) 

        # Dispara as outras Threads
        for i, texto_fatiado in enumerate(partes_texto[1:], start=2):
            t = threading.Thread(target=worker_geracao, args=(texto_fatiado, i))
            t.start()
            threads_geracao.append(t)

        # Consome em pipeline
        for i, t in enumerate(threads_geracao, start=1):
            t.join() 
            dados = resultados.get(i, {})
            processar_parte_audio(chat_id, dados.get("path"), i, total_partes, dados.get("topicos_str", ""))
            
    except Exception as e:
        logger.error(f"Erro Áudio Orquestrador: {e}")