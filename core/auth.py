import hashlib
import hmac
import logging
import os
import time
from typing import Optional

from models import User, Sessao, Materia

logger = logging.getLogger(__name__)

# Segredo carregado do ambiente — nunca hardcoded
_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


# ──────────────────────────────────────────────
# 1. Validação de origem (HMAC do Telegram)
# ──────────────────────────────────────────────

def validar_requisicao_telegram(data: dict, hash_recebido: str) -> bool:
    """
    Verifica que a requisição veio realmente do Telegram, usando o HMAC
    descrito na documentação oficial de Login Widget / WebApp.

    `data` é o dicionário de campos da requisição (sem a chave 'hash').
    `hash_recebido` é o valor do campo 'hash' enviado pelo Telegram.
    """
    # Constrói a string de verificação em ordem alfabética
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items()) if k != "hash"
    )

    # A chave secreta é o SHA-256 do token do bot
    secret_key = hashlib.sha256(_BOT_TOKEN.encode()).digest()
    assinatura_esperada = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    # compare_digest previne timing attacks
    return hmac.compare_digest(assinatura_esperada, hash_recebido)


def validar_timestamp(auth_date: int, janela_segundos: int = 300) -> bool:
    """Rejeita tokens com mais de `janela_segundos` de idade (padrão: 5 min)."""
    return (time.time() - auth_date) <= janela_segundos


# ──────────────────────────────────────────────
# 2. Sessão com token rotativo assinado
# ──────────────────────────────────────────────

def _gerar_session_token(user_id: int, chat_id: str) -> str:
    """HMAC(bot_token, user_id + chat_id + timestamp)."""
    payload = f"{user_id}:{chat_id}:{int(time.time())}".encode()
    return hmac.new(
        _BOT_TOKEN.encode(), payload, hashlib.sha256
    ).hexdigest()


def _verificar_session_token(
    token: str,
    user_id: int,
    chat_id: str,
    criado_em: float,
    ttl_segundos: int = 3600,
) -> bool:
    """
    Confere que o token não foi forjado e ainda está dentro do TTL.
    Retorna False silenciosamente — o caller decide o que fazer.
    """
    if (time.time() - criado_em) > ttl_segundos:
        return False

    payload = f"{user_id}:{chat_id}:{int(criado_em)}".encode()
    esperado = hmac.new(
        _BOT_TOKEN.encode(), payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(esperado, token)


# ──────────────────────────────────────────────
# 3. Rate limiting simples em memória
# ──────────────────────────────────────────────

_tentativas: dict[str, list[float]] = {}
_MAX_TENTATIVAS = 5
_JANELA_RATE = 60  # segundos


def _rate_limit_ok(chat_id: str) -> bool:
    agora = time.time()
    historico = [t for t in _tentativas.get(chat_id, []) if agora - t < _JANELA_RATE]
    _tentativas[chat_id] = historico

    if len(historico) >= _MAX_TENTATIVAS:
        logger.warning(f"Rate limit atingido para chat_id={chat_id}")
        return False

    _tentativas[chat_id].append(agora)
    return True


# ──────────────────────────────────────────────
# 4. Função principal
# ──────────────────────────────────────────────

def obter_sessao_usuario(
    db,
    chat_id: str | int,
    telegram_data: Optional[dict] = None,
    hash_telegram: Optional[str] = None,
) -> tuple:
    """
    Busca ou cria o usuário e a sessão com múltiplas camadas de proteção.

    Parâmetros:
        db             — sessão SQLAlchemy
        chat_id        — ID do chat do Telegram
        telegram_data  — dict com os campos vindos do Telegram (inclui auth_date)
        hash_telegram  — campo 'hash' enviado pelo Telegram para validação HMAC

    Retorna: (user, sessao, materia_nome)
    Lança:   PermissionError em qualquer falha de autenticação
    """
    chat_id = str(chat_id)

    # 3. Rate limit antes de qualquer I/O
    if not _rate_limit_ok(chat_id):
        raise PermissionError("Muitas tentativas. Tente novamente em instantes.")

    # 1. Valida que a requisição veio do Telegram (quando os dados estão disponíveis)
    if telegram_data and hash_telegram:
        if not validar_requisicao_telegram(telegram_data, hash_telegram):
            logger.warning(f"Falha HMAC para chat_id={chat_id}")
            raise PermissionError("Requisição inválida.")

        auth_date = telegram_data.get("auth_date", 0)
        if not validar_timestamp(int(auth_date)):
            logger.warning(f"Token expirado para chat_id={chat_id}")
            raise PermissionError("Token expirado. Faça login novamente.")

    needs_commit = False

    user = db.query(User).filter_by(telegram_id=chat_id).first()
    if not user:
        user = User(telegram_id=chat_id)
        db.add(user)
        db.flush()
        needs_commit = True

    sessao = db.query(Sessao).filter_by(user_id=user.id).first()
    if not sessao:
        token = _gerar_session_token(user.id, chat_id)
        sessao = Sessao(user_id=user.id, session_token=token, token_criado_em=time.time())
        db.add(sessao)
        needs_commit = True
    else:
        # 2. Verifica o token da sessão existente
        token_valido = _verificar_session_token(
            sessao.session_token,
            user.id,
            chat_id,
            sessao.token_criado_em,
        )
        if not token_valido:
            # Rotaciona o token em vez de bloquear — sessão legítima que expirou
            sessao.session_token = _gerar_session_token(user.id, chat_id)
            sessao.token_criado_em = time.time()
            needs_commit = True

    if needs_commit:
        db.commit()
        db.refresh(user)
        db.refresh(sessao)

    materia_nome = "Nenhuma"
    if sessao.materia_ativa:
        m_ativa = db.query(Materia).get(sessao.materia_ativa)
        if m_ativa:
            materia_nome = m_ativa.nome

    return user, sessao, materia_nome