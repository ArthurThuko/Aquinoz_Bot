from groq import Groq
from config import GROQ_TOKEN

client = Groq(api_key=GROQ_TOKEN)

def pedir_ia(prompt, contexto):
    contexto_limpo = " ".join(contexto.split())[:7000] 

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é um tutor de estudos objetivo. Regras:\n"
                        "1. Use APENAS o contexto fornecido.\n"
                        "2. Se a informação não estiver lá, diga 'Não encontrado'.\n"
                        "3. Vá direto ao ponto, sem introduções ou saudações."
                    )
                },
                {
                    "role": "user",
                    "content": f"Contexto: {contexto_limpo}\n\nTarefa: {prompt}"
                }
            ],
            model="llama-3.1-8b-instant",
            temperature=0.4,
            max_tokens=1500
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Erro na IA: {e}"