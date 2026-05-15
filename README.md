# Aquinoz_Bot

▶️ 2. Rodar o servidor Flask
python app.py

Você verá:

Running on http://127.0.0.1:5000

🌐 3. Expor API com ngrok

Em outro terminal:

ngrok http 5000

Vai gerar algo como:

https://abc123.ngrok-free.app

🔗 4. Configurar o Webhook

Abra no navegador:

https://api.telegram.org/botSEU_TOKEN/setWebhook?url=https://abc123.ngrok-free.app/webhook

✅ Resposta esperada
{
  "ok": true,
  "result": true,
  "description": "Webhook was set"
}