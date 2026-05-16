from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

engine = create_engine('sqlite:///database.db')
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True)

class Materia(Base):
    __tablename__ = "materias"
    id = Column(Integer, primary_key=True)
    nome = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"))

class Conteudo(Base):
    __tablename__ = "conteudos"
    id = Column(Integer, primary_key=True)
    texto = Column(String)
    tipo = Column(String)  # texto, imagem, audio
    materia_id = Column(Integer, ForeignKey("materias.id"))

class Sessao(Base):
    __tablename__ = "sessao"
    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    materia_ativa = Column(Integer, ForeignKey("materias.id"))
    editando_materia_id = Column(Integer, nullable=True)

Base.metadata.create_all(engine)