import os
import logging
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Tipos de imagem permitidos (whitelist de extensões)
EXTENSOES_PERMITIDAS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

def _validar_caminho(caminho_arquivo: str) -> Path:
    """Valida o caminho e evita path traversal."""
    path = Path(caminho_arquivo).resolve()

    if path.suffix.lower() not in EXTENSOES_PERMITIDAS:
        raise ValueError(f"Tipo de arquivo não permitido: {path.suffix}")

    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    return path


def _preprocessar_imagem(img: Image.Image) -> Image.Image:
    """
    Aplica pipeline de pré-processamento para maximizar a qualidade do OCR:
    grayscale → denoising → contraste → sharpness → binarização adaptativa.
    """
    # 1. Converter para RGB para garantir compatibilidade, depois grayscale
    img = img.convert("RGB")
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)

    # 2. Denoising (reduz ruído sem borrar bordas de texto)
    img_cv = cv2.fastNlMeansDenoising(img_cv, h=15)

    # 3. Aumentar resolução se a imagem for pequena (OCR funciona melhor com +300 DPI)
    altura, largura = img_cv.shape
    if largura < 1000:
        escala = 1000 / largura
        img_cv = cv2.resize(
            img_cv,
            (int(largura * escala), int(altura * escala)),
            interpolation=cv2.INTER_CUBIC,
        )

    # 4. Binarização adaptativa (lida bem com iluminação irregular)
    img_bin = cv2.adaptiveThreshold(
        img_cv,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    # 5. Morfologia: fecha pequenas brechas nos caracteres
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    img_bin = cv2.morphologyEx(img_bin, cv2.MORPH_CLOSE, kernel)

    # Volta para PIL para aplicar Enhance
    img_pil = Image.fromarray(img_bin)

    # 6. Contraste extra via PIL
    img_pil = ImageEnhance.Contrast(img_pil).enhance(2.0)

    # 7. Sharpening leve para destacar bordas de caracteres
    img_pil = img_pil.filter(ImageFilter.SHARPEN)

    return img_pil


def extrair_texto_imagem(caminho_arquivo: str) -> str:
    """
    Extrai texto de uma imagem usando Tesseract OCR com pré-processamento avançado.
    Retorna string vazia em caso de falha (sem lançar exceção para o caller).
    """
    try:
        path = _validar_caminho(caminho_arquivo)
        img_original = Image.open(path)

        # Tenta primeiro com pré-processamento
        img_processada = _preprocessar_imagem(img_original)
        config_tesseract = "--oem 3 --psm 6"  # LSTM + bloco de texto uniforme
        texto = pytesseract.image_to_string(
            img_processada, lang="por", config=config_tesseract
        )

        # Fallback: se não extraiu nada, tenta a imagem original em escala de cinza
        if not texto.strip():
            logger.warning("Pré-processamento não gerou texto; tentando imagem original.")
            img_gray = img_original.convert("L")
            texto = pytesseract.image_to_string(
                img_gray, lang="por", config=config_tesseract
            )

        return texto.strip()

    except (ValueError, FileNotFoundError) as e:
        logger.error(f"Erro de validação na imagem: {e}")
        return ""
    except pytesseract.TesseractNotFoundError:
        logger.error(
            "Tesseract não encontrado. Instale-o e garanta que está no PATH do sistema."
        )
        return ""
    except Exception as e:
        logger.error(f"Erro inesperado ao ler imagem: {e}", exc_info=True)
        return ""