import time
import threading
import requests
from functools import wraps
from services.telegram import send_message

# --- 📊 ARQUITETURA DE TELEMETRIA (COM DADOS GLOBAIS) ---
metricas = threading.local()

# Agora o histórico armazena objetos completos para expor no ranking
historico_telemetria = []
contador_global = 0
total_tokens_global = 0
total_kb_global = 0.0

lock_telemetria = threading.Lock()

def registrar_trafego_rede(bytes_quantidade):
    """Função utilitária para interceptar o tamanho real das requisições HTTP."""
    try:
        if hasattr(metricas, 'kb'):
            metricas.kb += bytes_quantidade / 1024
    except Exception:
        pass

# --- 🐵 MONKEY-PATCHING: Interceptador de Rede Global (Método 2) ---
# Salva as funções originais do requests
_original_request = requests.request
_original_get = requests.get
_original_post = requests.post

def _patched_request(method, url, **kwargs):
    """Mede os bytes de entrada e saída e chama a função original."""
    response = _original_request(method, url, **kwargs)
    
    # Calcula os bytes enviados (payload)
    tamanho_saida = len(str(kwargs.get('data', ''))) + len(str(kwargs.get('json', '')))
    
    # Calcula os bytes recebidos (headers da resposta + conteúdo binário)
    tamanho_entrada = len(response.content) + len(str(response.headers))
    
    # Joga no contador da Thread atual
    registrar_trafego_rede(tamanho_saida + tamanho_entrada)
    return response

# Sobrescreve as funções globais na memória para o resto do sistema
requests.request = _patched_request
requests.get = lambda url, **kwargs: _patched_request('get', url, **kwargs)
requests.post = lambda url, **kwargs: _patched_request('post', url, **kwargs)
# -------------------------------------------------------------------

def telemetria(func):
    """Decorator que captura tempo, dados de rede, tokens e histórico detalhado."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        global contador_global, total_tokens_global, total_kb_global
        
        chat_id = args[0]
        metricas.tokens = 0
        metricas.kb = 0.0
        
        inicio = time.time()
        resultado = func(*args, **kwargs)
        duracao = time.time() - inicio
        
        with lock_telemetria:
            contador_global += 1
            exec_id = contador_global
            nome_tarefa = f"{func.__name__} #{exec_id}"
            
            # Salva os dados independentes de cada execução no histórico
            dados_execucao = {
                "tarefa": nome_tarefa,
                "tempo": duracao,
                "tokens": metricas.tokens,
                "kb": metricas.kb
            }
            historico_telemetria.append(dados_execucao)
            
            # Ordena do mais lento para o mais rápido
            ranking_ordenado = sorted(historico_telemetria, key=lambda x: x["tempo"], reverse=True)
            
            total_tokens_global += metricas.tokens
            total_kb_global += metricas.kb
            
            snap_tokens_totais = total_tokens_global
            snap_kb_total = total_kb_global
            snap_media_kb = total_kb_global / contador_global

        # Monta a renderização
        msg = f"📊 <b>[Observabilidade: {func.__name__} #{exec_id}]</b>\n\n"
        msg += f"⏱️ <b>Tempo da execução:</b> {duracao:.2f}s\n"
        
        if metricas.tokens > 0 or metricas.kb > 0:
            msg += "\n📌 <b>Gasto Atual:</b>\n"
            if metricas.tokens > 0:
                msg += f"  • Tokens: {metricas.tokens}\n"
            if metricas.kb > 0:
                msg += f"  • Tráfego I/O: {metricas.kb:.2f} KB\n"
        
        msg += "\n🌍 <b>Métricas Globais (Acumulado):</b>\n"
        msg += f"  • <b>Total Execuções:</b> {contador_global}\n"
        msg += f"  • <b>Total Tokens:</b> {snap_tokens_totais}\n"
        msg += f"  • <b>Total Tráfego:</b> {snap_kb_total:.2f} KB\n"
        msg += f"  • <b>Média de Tráfego:</b> {snap_media_kb:.2f} KB/req\n"
            
        msg += "\n<b>🏆 Ranking Histórico (Top 15 Lentos):</b>\n"
        
        # Exibe os detalhes individuais de cada tarefa no ranking
        for i, item in enumerate(ranking_ordenado[:15], 1):
            linha = f"{item['tarefa']}: {item['tempo']:.2f}s | 🪙 {item['tokens']} tk | 🛜 {item['kb']:.2f} KB"
            if i == 1:
                msg += f"🔴 {i}. {linha}\n"
            elif i <= 3:
                msg += f"🟡 {i}. {linha}\n"
            else:
                msg += f"🟢 {i}. {linha}\n"
            
        send_message(chat_id, msg)
        return resultado
    return wrapper