from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

engine = create_engine(
    "sqlite:///database.db",
    connect_args={"check_same_thread": False},  # necessário para SQLite com Flask/threads
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id          = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False, index=True)

    materias = relationship("Materia", back_populates="user", cascade="all, delete")
    sessao   = relationship("Sessao",  back_populates="user", uselist=False, cascade="all, delete")


class Materia(Base):
    __tablename__ = "materias"

    id      = Column(Integer, primary_key=True)
    nome    = Column(String,  nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    user      = relationship("User",     back_populates="materias")
    conteudos = relationship("Conteudo", back_populates="materia", cascade="all, delete")


class Conteudo(Base):
    __tablename__ = "conteudos"

    id         = Column(Integer, primary_key=True)
    texto      = Column(String,  nullable=False)
    tipo       = Column(String,  nullable=False)  # "texto" | "imagem" | "pdf" | "link"
    materia_id = Column(Integer, ForeignKey("materias.id", ondelete="CASCADE"), nullable=False)

    materia = relationship("Materia", back_populates="conteudos")


class Sessao(Base):
    __tablename__ = "sessoes"

    id                  = Column(Integer, primary_key=True)
    user_id             = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    materia_ativa       = Column(Integer, ForeignKey("materias.id", ondelete="SET NULL"), nullable=True)
    editando_materia_id = Column(Integer, nullable=True)
    session_token       = Column(String(64), nullable=True)
    token_criado_em     = Column(Float,      nullable=True)

    user = relationship("User", back_populates="sessao")


Base.metadata.create_all(engine)