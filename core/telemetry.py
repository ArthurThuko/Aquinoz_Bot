import threading
import requests
from functools import wraps

# Mantemos as estruturas na memória para que os outros arquivos não deem erro de import
metricas = threading.local()
historico_telemetria = []
contador_global = 0
total_tokens_global = 0
total_kb_global = 0.0
lock_telemetria = threading.Lock()

def registrar_trafego_rede(bytes_quantidade):
    """Silenicidado: Não faz nada com os bytes recebidos."""
    pass

# --- MONKEY-PATCHING DESATIVADO ---
# Não alteramos as funções globais do requests para economizar processamento
# ----------------------------------

def telemetria(func):
    """Decorator Neutro: Apenas executa a função original, desativando os logs."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Inicializa as variáveis locais para evitar erros caso alguma task tente ler
        metricas.tokens = 0
        metricas.kb = 0.0
        
        # Executa a função e retorna o resultado direto (Sem calcular tempo ou enviar msg)
        return func(*args, **kwargs)
    return wrapper