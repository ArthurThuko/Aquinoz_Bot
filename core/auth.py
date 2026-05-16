from models import User, Sessao, Materia

def obter_sessao_usuario(db, chat_id):
    """
    Busca ou cria o usuário e a sessão no banco de dados. 
    Retorna o objeto do usuário, da sessão e o nome da matéria ativa.
    """
    user = db.query(User).filter_by(telegram_id=str(chat_id)).first()
    needs_commit = False
    
    if not user:
        user = User(telegram_id=str(chat_id))
        db.add(user)
        db.flush() # Gera o ID sem o custo de rede de um commit final
        needs_commit = True

    sessao = db.query(Sessao).filter_by(user_id=user.id).first()
    if not sessao:
        sessao = Sessao(user_id=user.id)
        db.add(sessao)
        needs_commit = True

    if needs_commit:
        db.commit()
        db.refresh(user)
        db.refresh(sessao)

    materia_nome = "Nenhuma"
    if sessao.materia_ativa:
        m_ativa = db.query(Materia).get(sessao.materia_ativa)
        if m_ativa:
            materia_nome = m_ativa.nome

    return user, sessao, materia_nome