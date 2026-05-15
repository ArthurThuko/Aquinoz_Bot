import requests
from bs4 import BeautifulSoup

def extrair_texto_da_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            for s in soup(['script', 'style', 'nav', 'footer', 'header']):
                s.extract()
            texto = soup.get_text(separator=' ', strip=True)
            return texto[:4000] # Limite para não estourar o banco
    except:
        return None