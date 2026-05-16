import requests
from bs4 import BeautifulSoup
import re

def extrair_texto_da_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Remove o que não é conteúdo
            for s in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                s.extract()
            
            texto = soup.get_text(separator=' ')
            # Remove excesso de espaços e quebras de linha com Regex
            texto_limpo = re.sub(r'\s+', ' ', texto).strip()
            
            return texto_limpo[:6000] # Corta para caber no limite de tokens
    except:
        return None