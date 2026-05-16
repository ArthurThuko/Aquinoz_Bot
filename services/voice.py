import edge_tts
import asyncio
import os

def gerar_audio_do_texto(texto, user_id, indice=None):
    """
    Usa as vozes neurais gratuitas da Microsoft via Edge-TTS.
    Voz selecionada: Antonio (pt-BR).
    """
    # Adiciona a marcação da parte no nome do arquivo para evitar colisão entre as fatias
    sufixo = f"_parte_{indice}" if indice is not None else ""
    file_path = f"temp_voice_{user_id}{sufixo}.mp3"
    
    voice = "pt-BR-AntonioNeural" 
    
    async def run_tts():
        # Velocidade normal (sem rate) focada em acessibilidade e leitura acompanhada
        communicate = edge_tts.Communicate(texto, voice)
        await communicate.save(file_path)

    try:
        # Executa o loop assíncrono dentro da thread
        asyncio.run(run_tts())
        
        if os.path.exists(file_path):
            return file_path
    except Exception as e:
        print(f"Erro ao sintetizar voz com Antonio: {e}")
    
    return None