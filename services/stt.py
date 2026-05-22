# services/stt.py
import os
import re
from groq import Groq
from config import GROQ_TOKEN

# Inicializa o cliente da Groq com o token importado do arquivo central de configurações
client = Groq(api_key=GROQ_TOKEN)

def transcrever_audio(file_path):
    """
    Recebe o caminho de um arquivo de áudio local do Telegram (.ogg/.mp3)
    e retorna o texto transcrevido utilizando o Whisper na Groq.
    """
    if not os.path.exists(file_path):
        print(f"Erro: O arquivo {file_path} não foi encontrado.")
        return None

    try:
        with open(file_path, "rb") as audio_file:
            transcricao = client.audio.transcriptions.create(
                model="whisper-large-v3", 
                file=audio_file,
                language="pt"  # Fixar o idioma economiza processamento e evita erros de detecção
            )
            
        texto_bruto = transcricao.text
        return otimizar_texto_estudante(texto_bruto)

    except Exception as e:
        print(f"Erro ao transcrever áudio na Groq: {e}")
        return None


def otimizar_texto_estudante(texto):
    """
    Remove vícios de linguagem e hesitações comuns de áudio localmente,
    poupando dinheiro e tokens preciosos na janela de contexto da LLM.
    """
    if not texto:
        return ""
    
    # Mantém a caixa original para a checagem do comando, apenas normaliza os espaços
    texto_limpo = re.sub(r'\s+', ' ', texto).strip()
    return texto_limpo


def converter_fala_em_comando(texto):
    """
    Analisa o texto falado. Para ser um comando, a frase DEVE começar com "oi bot".
    Se começar, traduz para o comando equivalente (/resumir, /gerar_questoes, etc).
    Caso contrário, ignora a interceptação e devolve o texto original.
    """
    if not texto:
        return ""
        
    # Coloca em minúsculo e remove espaços nas pontas para padronizar a checagem
    texto_min = texto.lower().strip()
    
    # 🎯 ATUALIZADO: Nova palavra-chave mais simples para o Whisper não errar
    palavra_chave = "oi bot"
    
    # VALIDAÇÃO CRÍTICA: Só entra na checagem se começar exatamente com o termo
    if texto_min.startswith(palavra_chave):
        # Remove a palavra de ativação e possíveis vírgulas/espaços do início da frase restante
        # Ex: "oi bot, resumir psu" vira "resumir psu"
        comando_limpo = texto_min[len(palavra_chave):].strip(",. ")
        
        # Mapeamento de intenções por voz após o gatilho
        if "resumir" in comando_limpo or "resumo" in comando_limpo:
            return "/resumir"
            
        if "questões" in comando_limpo or "questoes" in comando_limpo or "gerar questoes" in comando_limpo:
            return "/gerar_questoes"
            
        if "conteúdos" in comando_limpo or "conteudos" in comando_limpo:
            return "/conteudos"
            
        if "ajuda" in comando_limpo or "socorro" in comando_limpo:
            return "/ajuda"
            
        if "menu" in comando_limpo:
            return "/menu"
            
        if "disciplinas" in comando_limpo or "matérias" in comando_limpo or "materias" in comando_limpo:
            return "/materias"

    # Se não começar com "Oi Bot" ou não bater com nenhum comando, 
    # retorna o texto original seguro para ser processado como conteúdo ou dúvida.
    return texto
    """
    Analisa o texto falado. Para ser um comando, a frase DEVE começar com "oi aquinoz".
    Se começar, traduz para o comando equivalente (/resumir, /gerar_questoes, etc).
    Caso contrário, ignora a interceptação e devolve o texto original.
    """
    if not texto:
        return ""
        
    # Coloca em minúsculo e remove espaços nas pontas para padronizar a checagem
    texto_min = texto.lower().strip()
    
    palavra_chave = "oi aquinoz"
    
    # 🎯 VALIDAÇÃO CRÍTICA: Só entra na checagem se começar exatamente com o termo
    if texto_min.startswith(palavra_chave):
        # Remove a palavra de ativação e possíveis vírgulas/espaços do início da frase restante
        # Ex: "oi aquinoz, resumir psu" vira "resumir psu"
        comando_limpo = texto_min[len(palavra_chave):].strip(",. ")
        
        # Mapeamento de intenções por voz após o gatilho
        if "resumir" in comando_limpo or "resumo" in comando_limpo:
            return "/resumir"
            
        if "questões" in comando_limpo or "questoes" in comando_limpo or "gerar questoes" in comando_limpo:
            return "/gerar_questoes"
            
        if "conteúdos" in comando_limpo or "conteudos" in comando_limpo:
            return "/conteudos"
            
        if "ajuda" in comando_limpo or "socorro" in comando_limpo:
            return "/ajuda"
            
        if "menu" in comando_limpo:
            return "/menu"
            
        if "disciplinas" in comando_limpo or "matérias" in comando_limpo or "materias" in comando_limpo:
            return "/materias"

    # Se não começar com "Oi Aquinoz" ou não bater com nenhum comando, 
    # retorna o texto original seguro para ser processado como conteúdo ou dúvida.
    return texto