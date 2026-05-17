import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from PIL import Image

def extrair_texto_imagem(caminho_arquivo):
    try:
        img = Image.open(caminho_arquivo)
        texto = pytesseract.image_to_string(img, lang="por")  # português
        return texto
    except Exception as e:
        print(f"Erro ao ler imagem: {e}")
        return ""