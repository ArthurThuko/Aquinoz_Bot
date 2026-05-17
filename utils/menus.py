MENU_PRINCIPAL = {
    "inline_keyboard": [
        [{"text": "📊 Resumir", "callback_data": "/resumir"}, {"text": "📝 Questoes", "callback_data": "/gerar_questoes"}],
        [{"text": "📚 Minhas Materias", "callback_data": "/materias"}, {"text": "➕ Nova Materia", "callback_data": "/nova_materia"}],
        [{"text": "📖 Conteúdos", "callback_data": "/conteudos"}, {"text": "💡 Ajuda", "callback_data": "/ajuda"}]
    ]
}

TEXTO_AJUDA = (
    "<b>💡 O SEGREDO DO FUNCIONAMENTO</b>\n\n"
    "Eu sou um <b>assistente de organização</b>, não um criador de conteúdo. "
    "<u>Não consigo fazer nada sem que você envie a matéria primeiro.</u> "
    "Eu não invento informações; eu processo o que você me manda para facilitar seu estudo.\n\n"
    "<b>❓ COMO FALAR COMIGO?</b>\n"
    "• <b>Perguntas:</b> Termine qualquer frase com <b>'?'</b>. Eu vou vasculhar seus textos salvos.\n"
    "• <b>Comandos:</b> Qualquer mensagem que comece com <code>/</code>.\n"
    "• <b>Conteúdo:</b> Tudo o que digitar (que não termine com '?' e sem /) será <b>salvo automaticamente</b>.\n\n"
    "<b>🚀 PASSO A PASSO RÁPIDO</b>\n"
    "1. Use <code>/add Nome</code> para criar a disciplina.\n"
    "2. Em <b>Minhas Matérias</b>, selecione a que deseja alimentar.\n"
    "3. Mande textos, links ou PDFs.\n"
    "4. Use o <b>/menu</b> para gerar resumos e testes."
)