from pypdf import PdfReader

def extrair_texto_pdf(caminho_arquivo):
    texto = ""

    try:
        reader = PdfReader(caminho_arquivo)

        for pagina in reader.pages:
            texto += pagina.extract_text() or ""

    except Exception as e:
        print(f"Erro ao ler PDF: {e}")

    return texto