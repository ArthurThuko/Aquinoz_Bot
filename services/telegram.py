import requests
from config import BASE_URL

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    # 👇 adiciona suporte a botões
    if reply_markup:
        payload["reply_markup"] = reply_markup

    response = requests.post(f"{BASE_URL}/sendMessage", json=payload)
    
    if response.status_code != 200:
        print(f"Erro do Telegram: {response.text}")
        
    return response

def send_voice(chat_id, file_path):
    url = f"{BASE_URL}/sendVoice"
    with open(file_path, 'rb') as voice_file:
        payload = {"chat_id": chat_id}
        files = {"voice": voice_file}
        return requests.post(url, data=payload, files=files)
    