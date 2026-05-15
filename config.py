import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN não definido no .env")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"