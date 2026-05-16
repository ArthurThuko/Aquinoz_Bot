def chunk_text(text: str, max_chars: int = 1000, overlap: int = 100) -> list:
    if not text: return []
    chunks, start, text_length = [], 0, len(text)

    while start < text_length:
        end = start + max_chars
        if end < text_length:
            last_space = text.rfind(' ', start, end)
            if last_space != -1 and (end - last_space) < 50: 
                end = last_space

        chunk = text[start:end].strip()
        if chunk: chunks.append(chunk)
        start = end - overlap
        if start <= 0 or end == text_length:
            if end == text_length: break
    return chunks