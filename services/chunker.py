import re

# Marcadores improváveis de aparecer em texto natural
_OVL_INI = "\u27e6OVL\u27e7"   # ⟦OVL⟧
_OVL_FIM = "\u27e6/OVL\u27e7"  # ⟦/OVL⟧

_RE_OVL = re.compile(
    re.escape(_OVL_INI) + ".*?" + re.escape(_OVL_FIM),
    re.DOTALL,
)


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 100) -> list[str]:
    if not text:
        return []

    chunks      = []
    start       = 0
    text_length = len(text)

    while start < text_length:
        end = start + max_chars

        # Quebra na última palavra se não estiver próximo do fim
        if end < text_length:
            last_space = text.rfind(" ", start, end)
            if last_space != -1 and (end - last_space) < 50:
                end = last_space

        trecho = text[start:end].strip()
        if not trecho:
            break

        # ── Marca zona de overlap no INÍCIO (zona compartilhada com chunk anterior) ──
        if start > 0 and len(trecho) > overlap:
            trecho = _OVL_INI + trecho[:overlap] + _OVL_FIM + trecho[overlap:]

        # ── Marca zona de overlap no FIM (zona que o próximo chunk vai repetir) ──
        if end < text_length and len(trecho) > overlap:
            trecho = trecho[:-overlap] + _OVL_INI + trecho[-overlap:] + _OVL_FIM

        chunks.append(trecho)

        start = end - overlap
        if end >= text_length:
            break

    return chunks


def limpar_overlaps(texto: str) -> str:
    """Remove as zonas de overlap. Use antes de exibir qualquer chunk ao usuário."""
    return _RE_OVL.sub("", texto).strip()