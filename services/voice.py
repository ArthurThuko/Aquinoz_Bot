import edge_tts
import asyncio
import os

def gerar_audio_do_texto(texto, user_id):
    """
    Usa as vozes neurais gratuitas da Microsoft via Edge-TTS.
    Voz selecionada: Antonio (pt-BR).
    """
    file_path = f"temp_voice_{user_id}.mp3"
    
    # ID exato da voz do Antonio
    voice = "pt-BR-AntonioNeural" 
    
    async def run_tts():
        # Limitamos a 3000 caracteres para garantir rapidez e estabilidade
        communicate = edge_tts.Communicate(texto[:3000], voice)
        await communicate.save(file_path)

    try:
        # Executa o loop assíncrono dentro da thread do Flask
        asyncio.run(run_tts())
        
        if os.path.exists(file_path):
            return file_path
    except Exception as e:
        print(f"Erro ao sintetizar voz com Antonio: {e}")
    
    return None