from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, Integer, ForeignKey, Enum, \
    UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
import random
import string
from contextlib import contextmanager

# Создаем базовый класс для моделей
Base = declarative_base()


# Модель пользователя
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone_number = Column(String(20), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "phone_number": self.phone_number,
            "email": self.email,
            "username": self.username,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# Модель задачи (личные задачи)
class Todo(Base):
    __tablename__ = "todos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    completed = Column(Boolean, default=False)
    user_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# Модель для хранения кодов подтверждения
class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone_number = Column(String(20), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    code = Column(String(10), nullable=False)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)


# Модель команды
class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    owner_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])


# Модель участника команды
class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String(36), ForeignKey('teams.id'), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    role = Column(Enum('owner', 'co_owner', 'member', name='team_roles'), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    team = relationship("Team")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint('team_id', 'user_id', name='unique_team_member'),
        Index('ix_team_members_team_user', 'team_id', 'user_id'),
    )


# Модель задачи команды
class TeamTask(Base):
    __tablename__ = "team_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    team_id = Column(String(36), ForeignKey('teams.id'), nullable=False, index=True)
    created_by = Column(String(36), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    team = relationship("Team")
    creator = relationship("User", foreign_keys=[created_by])


# Модель для отметок выполнения командных задач
class TeamTaskCompletion(Base):
    __tablename__ = "team_task_completions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey('team_tasks.id'), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)
    completed_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    task = relationship("TeamTask")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint('task_id', 'user_id', name='unique_task_completion'),
        Index('ix_task_completion_task_user', 'task_id', 'user_id'),
    )


# Подключение к SQLite базе данных
SQLALCHEMY_DATABASE_URL = "sqlite:///./todos.db"

# Создаем движок
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Создаем таблицы
Base.metadata.create_all(bind=engine)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Зависимость для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Контекстный менеджер для транзакций
@contextmanager
def transaction(db: SessionLocal):
    """Контекстный менеджер для безопасных транзакций"""
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


# Безопасная генерация никнейма (исправление SQL injection и race condition)
def generate_default_username(db: SessionLocal) -> str:
    """Генерирует безопасный случайный никнейм"""
    max_attempts = 10

    for attempt in range(max_attempts):
        # Генерируем случайный суффикс
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        username = f"user_{suffix}"

        # Проверяем уникальность
        existing_user = db.query(User).filter(User.username == username).first()
        if not existing_user:
            return username

    # Если все попытки исчерпаны, используем UUID
    return f"user_{uuid.uuid4().hex[:8]}"