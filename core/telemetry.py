import threading
import time
import logging
from functools import wraps
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Estruturas de dados
# ──────────────────────────────────────────────

@dataclass
class RegistroTelemetria:
    funcao:        str
    duracao_ms:    float
    tokens:        int
    kb:            float
    sucesso:       bool
    erro:          str | None = None
    timestamp:     float = field(default_factory=time.time)


@dataclass
class ResumoGlobal:
    chamadas:      int   = 0
    erros:         int   = 0
    tokens:        int   = 0
    kb:            float = 0.0
    duracao_ms:    float = 0.0  # acumulada


# ──────────────────────────────────────────────
# Estado global (thread-safe)
# ──────────────────────────────────────────────

metricas         = threading.local()   # por thread: metricas.tokens, metricas.kb
_lock            = threading.Lock()
_historico:  list[RegistroTelemetria] = []
_resumo          = ResumoGlobal()
_MAX_HISTORICO   = 500                 # evita crescimento ilimitado em memória


# ──────────────────────────────────────────────
# Acesso ao resumo (leitura externa)
# ──────────────────────────────────────────────

def obter_resumo() -> ResumoGlobal:
    """Retorna uma cópia snapshot do resumo global (thread-safe)."""
    with _lock:
        return ResumoGlobal(
            chamadas   = _resumo.chamadas,
            erros      = _resumo.erros,
            tokens     = _resumo.tokens,
            kb         = _resumo.kb,
            duracao_ms = _resumo.duracao_ms,
        )


def obter_historico(n: int = 20) -> list[RegistroTelemetria]:
    """Retorna os últimos `n` registros."""
    with _lock:
        return list(_historico[-n:])


def resetar() -> None:
    """Zera tudo — útil para testes."""
    global _resumo, _historico
    with _lock:
        _resumo   = ResumoGlobal()
        _historico = []


# ──────────────────────────────────────────────
# Decorator
# ──────────────────────────────────────────────

def telemetria(func: Callable) -> Callable:
    """
    Mede duração, tokens e KB de qualquer função sem alterar seu comportamento.
    As métricas por-chamada ficam em `metricas` (threading.local) durante a execução,
    permitindo que a função instrumentada acumule via `metricas.tokens += N`.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Reseta contadores locais desta thread para esta chamada
        metricas.tokens = 0
        metricas.kb     = 0.0

        inicio  = time.perf_counter()
        sucesso = True
        erro    = None

        try:
            resultado = func(*args, **kwargs)
            return resultado
        except Exception as exc:
            sucesso = False
            erro    = type(exc).__name__
            raise
        finally:
            duracao_ms = (time.perf_counter() - inicio) * 1000

            registro = RegistroTelemetria(
                funcao     = func.__qualname__,
                duracao_ms = round(duracao_ms, 2),
                tokens     = getattr(metricas, "tokens", 0),
                kb         = round(getattr(metricas, "kb", 0.0), 4),
                sucesso    = sucesso,
                erro       = erro,
            )

            with _lock:
                # Atualiza resumo global
                _resumo.chamadas   += 1
                _resumo.tokens     += registro.tokens
                _resumo.kb         += registro.kb
                _resumo.duracao_ms += duracao_ms
                if not sucesso:
                    _resumo.erros += 1

                # Histórico com tamanho máximo
                _historico.append(registro)
                if len(_historico) > _MAX_HISTORICO:
                    _historico.pop(0)

            logger.debug(
                "[telemetria] %s | %.0fms | %d tokens | %.2f KB | %s",
                func.__qualname__,
                duracao_ms,
                registro.tokens,
                registro.kb,
                "ok" if sucesso else f"ERRO({erro})",
            )

    return wrapper