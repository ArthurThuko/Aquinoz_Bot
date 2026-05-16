def limpar_texto(t):
    """Remove markdown e protege caracteres como < e > para o Telegram não rejeitar a mensagem, 
    mas preserva as tags HTML de negrito biônico."""
    # 1. Remove formatações antigas de markdown
    t = t.replace("*", "").replace("_", "").replace("#", "").replace("`", "")
    
    # 2. Escapa tudo por segurança (evita crash com códigos como 'if x < y:')
    t = t.replace("<", "&lt;").replace(">", "&gt;")
    
    # 3. O Pulo do Gato: Restaura estritamente as tags que o bot precisa renderizar
    t = t.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    t = t.replace("&lt;B&gt;", "<b>").replace("&lt;/B&gt;", "</b>")
    
    return t

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