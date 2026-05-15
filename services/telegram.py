import requests
from config import BASE_URL
import html # Importe isso

def send_message(chat_id, text):
    # Opcional: Se o erro for 'Can't parse entities', 
    # tente remover o parse_mode temporariamente para testar
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML" 
    }
    response = requests.post(f"{BASE_URL}/sendMessage", json=payload)
    
    # Isso vai printar no seu terminal o erro real que o Telegram está devolvendo
    if response.status_code != 200:
        print(f"Erro do Telegram: {response.text}")
        
    return response