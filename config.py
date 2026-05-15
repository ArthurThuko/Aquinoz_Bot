import os
from dotenv import load_dotenv

load_dotenv()

# Lendo o Token do Telegram
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN não definido no .env")

# Lendo o Token do Groq
GROQ_TOKEN = os.getenv("GROQ_TOKEN")
if not GROQ_TOKEN:
    # É bom avisar se esquecer de colocar no .env
    print("Aviso: GROQ_TOKEN não definido. Funções de IA não vão funcionar.")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"