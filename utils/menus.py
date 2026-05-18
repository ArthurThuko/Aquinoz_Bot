MENU_PRINCIPAL = {
    "inline_keyboard": [
        [{"text": "📊 Resumir", "callback_data": "/resumir"}, {"text": "📝 Questoes", "callback_data": "/gerar_questoes"}],
        [{"text": "📚 Minhas Materias", "callback_data": "/materias"}, {"text": "➕ Nova Materia", "callback_data": "/nova_materia"}],
        [{"text": "📖 Conteúdos", "callback_data": "/conteudos"}, {"text": "💡 Ajuda", "callback_data": "/ajuda"}]
    ]
}

TEXTO_AJUDA = (
    "<b>🧠 AQUINOZ: SEU CÉREBRO EXTERNO</b>\n"
    "────────────────────────\n"
    "Eu sou uma <b>extensão da sua memória</b>. Eu processo seus arquivos "
    "para que você não precise reler tudo do zero. Eu aprendo com o que você me envia.\n\n"

    "<b>📱 NAVEGAÇÃO RÁPIDA</b>\n"
    "• <b>Botão de Menu:</b> Ao lado do campo de digitar, existe um ícone de <b>[Menu]</b> ou <b>[Quadradinho]</b>. "
    "Ele abre o painel principal de qualquer lugar da conversa.\n"
    "• <b>Onde estou?:</b> Para confirmar qual matéria está ativa, basta abrir o <b>Menu</b>. O nome dela será sempre a <b>primeira informação</b> no topo da mensagem.\n\n"

    "<b>📥 ALIMENTAÇÃO AUTOMÁTICA</b>\n"
    "• <b>Basta Enviar:</b> Não precisa de comandos para salvar. Envie <b>Texto, Link, PDF ou Imagem</b> "
    "a qualquer momento e eu salvarei automaticamente na matéria que estiver ativa.\n\n"

    "<b>💡 DICA DE OURO: GRANULARIDADE</b>\n"
    "• <b>Separe os Temas:</b> Para melhor eficiência, evite matérias genéricas. Em vez de 'Matemática', "
    "crie uma para <b>'Álgebra'</b> e outra para <b>'Geometria'</b>. "
    "Quanto mais focado o material, <b>mais precisas</b> serão minhas respostas!\n\n"

    "<b>📊 FERRAMENTAS DE ESTUDO</b>\n"
    "• <b>Resumir:</b> Transforma o material em tópicos didáticos com exemplos.\n"
    "• <b>Questões:</b> Gera testes de fixação baseados no seu material.\n"
    "• <b>Dúvida Direta:</b> Digite sua pergunta e termine com <b>'?'</b>.\n\n"
    
    "<b>🚀 PASSO A PASSO</b>\n"
    "1️⃣ Use <b>➕ Nova Matéria</b> para criar um tópico.\n"
    "2️⃣ Em <b>📚 Minhas Matérias</b>, selecione a desejada.\n"
    "3️⃣ Envie o conteúdo (PDF, Link ou Texto).\n"
    "4️⃣ Use o <b>📊 Resumir</b> para gerar seu guia de estudos.\n\n"

    "────────────────────────\n"
    "<i>Foco no estudo, eu cuido da organização!</i>"
)