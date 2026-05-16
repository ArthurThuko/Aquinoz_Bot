def limpar_texto(t):
    """Remove markdown e protege caracteres como < e > para o Telegram não rejeitar a mensagem."""
    t = t.replace("*", "").replace("_", "").replace("#", "").replace("`", "")
    return t.replace("<", "&lt;").replace(">", "&gt;")

def dividir_texto_em_partes(texto, limite=900):
    """
    Divide o texto sem cortar as palavras no meio. 
    Tenta quebrar por parágrafos duplos.
    """
    paragrafos = texto.split('\n\n')
    partes = []
    bloco_atual = ""

    for p in paragrafos:
        if len(bloco_atual) + len(p) > limite and bloco_atual:
            partes.append(bloco_atual.strip())
            bloco_atual = p + "\n\n"
        else:
            bloco_atual += p + "\n\n"
            
    if bloco_atual:
        partes.append(bloco_atual.strip())
        
    return partes