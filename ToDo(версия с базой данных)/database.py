from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid

# Создаем базовый класс для моделей
Base = declarative_base()


# Модель пользователя
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone_number = Column(String(20), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    username = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "phone_number": self.phone_number,
            "email": self.email,
            "username": self.username,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# Модель задачи
class Todo(Base):
    __tablename__ = "todos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    completed = Column(Boolean, default=False)
    user_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


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


# Функция для генерации никнейма по умолчанию
def generate_default_username(db: SessionLocal) -> str:
    """Генерирует никнейм по умолчанию в формате 'пользователь123'"""
    user_count = db.query(User).count()
    base_username = "пользователь"

    # Пробуем найти свободный номер
    number = user_count + 1
    username = f"{base_username}{number}"

    # Проверяем, не занят ли ник
    while db.query(User).filter(User.username == username).first():
        number += 1
        username = f"{base_username}{number}"

    return username