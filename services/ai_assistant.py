from groq import Groq
from config import GROQ_TOKEN

client = Groq(api_key=GROQ_TOKEN)

def pedir_ia(prompt, contexto):
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é um assistente de estudos. Responda de forma simples e direta, sem usar markdown complexo."
                },
                {
                    "role": "user",
                    "content": f"Contexto: {contexto}\n\nTarefa: {prompt}"
                }
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Erro na IA: {e}"