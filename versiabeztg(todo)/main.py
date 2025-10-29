from typing import List, Optional
from uuid import uuid4, UUID
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import secrets
import time

app = FastAPI(
    title="Simple TodoList with Auth",
    description="API для управления задачами с аутентификацией по номеру телефона",
    version="1.0.0"
)

# Добавляем схему аутентификации для Swagger
security_scheme = HTTPBearer()
security = HTTPBearer()


# Модели данных
class TodoItem(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    completed: bool = False
    user_id: UUID


class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None


class PhoneRequest(BaseModel):
    phone_number: str


class CodeVerification(BaseModel):
    phone_number: str
    code: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: UUID


class User(BaseModel):
    id: UUID
    phone_number: str
    created_at: float


# "Базы данных" в памяти
todos_db = {}
users_db = {}
phone_codes_db = {}  # {phone_number: {"code": "123456", "expires_at": timestamp}}
active_tokens = {}  # {token: user_id}

# Конфигурация
CODE_LENGTH = 6
CODE_EXPIRY = 300  # 5 минут в секундах


# Модель для зависимостей
class UserAuth:
    def __init__(self, user_id: UUID):
        self.user_id = user_id


# Функции для работы с аутентификацией
def generate_code() -> str:
    """Генерирует шестизначный код"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(CODE_LENGTH)])


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserAuth:
    """Получает текущего пользователя по токену"""
    token = credentials.credentials
    if token not in active_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserAuth(user_id=active_tokens[token])


# Эндпоинты аутентификации
@app.post("/auth/request-code/")
async def request_code(phone_request: PhoneRequest):
    """Запрос кода для входа по номеру телефона"""
    phone_number = phone_request.phone_number

    # Генерируем код
    code = generate_code()
    expires_at = time.time() + CODE_EXPIRY

    # Сохраняем код
    phone_codes_db[phone_number] = {
        "code": code,
        "expires_at": expires_at,
        "attempts": 0
    }

    # В реальном приложении здесь была бы отправка SMS
    print(f"Код для {phone_number}: {code} (действителен 5 минут)")

    return {
        "message": "Код отправлен",
        "expires_in": CODE_EXPIRY
    }


@app.post("/auth/verify-code/", response_model=Token)
async def verify_code(code_verification: CodeVerification):
    """Верификация кода и вход/регистрация"""
    phone_number = code_verification.phone_number
    code = code_verification.code

    # Проверяем существование кода
    if phone_number not in phone_codes_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code not requested or expired"
        )

    code_data = phone_codes_db[phone_number]

    # Проверяем срок действия
    if time.time() > code_data["expires_at"]:
        del phone_codes_db[phone_number]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code expired"
        )

    # Проверяем код
    if code_data["code"] != code:
        code_data["attempts"] += 1
        if code_data["attempts"] >= 3:
            del phone_codes_db[phone_number]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many attempts, request new code"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code"
        )

    # Удаляем использованный код
    del phone_codes_db[phone_number]

    # Ищем или создаем пользователя
    user = None
    for user_id, user_data in users_db.items():
        if user_data.phone_number == phone_number:
            user = user_data
            break

    if not user:
        # Создаем нового пользователя
        user_id = uuid4()
        user = User(
            id=user_id,
            phone_number=phone_number,
            created_at=time.time()
        )
        users_db[user_id] = user

    # Генерируем токен
    token = secrets.token_urlsafe(32)
    active_tokens[token] = user.id

    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id
    )


@app.post("/auth/logout/")
async def logout(current_user: UserAuth = Depends(get_current_user)):
    """Выход из системы"""
    # Находим и удаляем токен пользователя
    tokens_to_remove = []
    for token, user_id in active_tokens.items():
        if user_id == current_user.user_id:
            tokens_to_remove.append(token)

    for token in tokens_to_remove:
        del active_tokens[token]

    return {"message": "Logged out successfully"}


# Защищенные эндпоинты Todo
@app.get("/")
def root():
    return {"message": "TodoList API with Auth - используйте /docs для тестирования"}


# Получить все задачи пользователя
@app.get("/todos/", response_model=List[TodoItem])
def get_all_todos(
        completed: Optional[bool] = None,
        current_user: UserAuth = Depends(get_current_user)
):
    user_todos = [todo for todo in todos_db.values() if todo.user_id == current_user.user_id]

    # Фильтрация по статусу выполнения
    if completed is not None:
        user_todos = [todo for todo in user_todos if todo.completed == completed]

    return user_todos


# Получить задачу по ID
@app.get("/todos/{todo_id}", response_model=TodoItem)
def get_todo(
        todo_id: UUID,
        current_user: UserAuth = Depends(get_current_user)
):
    if todo_id not in todos_db or todos_db[todo_id].user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todos_db[todo_id]


# Создать новую задачу
@app.post("/todos/", response_model=TodoItem, status_code=status.HTTP_201_CREATED)
def create_todo(
        todo: TodoCreate,
        current_user: UserAuth = Depends(get_current_user)
):
    todo_id = uuid4()
    new_todo = TodoItem(
        id=todo_id,
        title=todo.title,
        description=todo.description,
        user_id=current_user.user_id,
        completed=False
    )
    todos_db[todo_id] = new_todo
    return new_todo


# Обновить задачу
@app.put("/todos/{todo_id}", response_model=TodoItem)
def update_todo(
        todo_id: UUID,
        todo_update: TodoUpdate,
        current_user: UserAuth = Depends(get_current_user)
):
    if todo_id not in todos_db or todos_db[todo_id].user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Todo not found")

    existing_todo = todos_db[todo_id]

    # Обновляем только переданные поля
    update_data = todo_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing_todo, field, value)

    return existing_todo


# Удалить задачу
@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(
        todo_id: UUID,
        current_user: UserAuth = Depends(get_current_user)
):
    if todo_id not in todos_db or todos_db[todo_id].user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Todo not found")

    del todos_db[todo_id]
    return


# Отметить задачу как выполненную
@app.patch("/todos/{todo_id}/complete", response_model=TodoItem)
def complete_todo(
        todo_id: UUID,
        current_user: UserAuth = Depends(get_current_user)
):
    if todo_id not in todos_db or todos_db[todo_id].user_id != current_user.user_id:
        raise HTTPException(status_code=404, detail="Todo not found")

    todos_db[todo_id].completed = True
    return todos_db[todo_id]


# Инициализация тестовых данных (только для отладки)
@app.post("/todos/init-sample/")
def init_sample_todos(current_user: UserAuth = Depends(get_current_user)):
    sample_todos = [
        {"title": "Изучить FastAPI", "description": "Пройти tutorial"},
        {"title": "Купить продукты", "description": "Молоко, хлеб, яйца"},
        {"title": "Сделать домашку", "completed": True},
        {"title": "Позвонить маме"},
    ]

    # Удаляем только задачи текущего пользователя
    user_todo_ids = [todo_id for todo_id, todo in todos_db.items() if todo.user_id == current_user.user_id]
    for todo_id in user_todo_ids:
        del todos_db[todo_id]

    # Создаем тестовые задачи для текущего пользователя
    for todo_data in sample_todos:
        todo_id = uuid4()
        todos_db[todo_id] = TodoItem(
            id=todo_id,
            user_id=current_user.user_id,
            **todo_data
        )

    return {"message": f"Создано {len(sample_todos)} тестовых задач"}


# Эндпоинт для получения информации о текущем пользователе
@app.get("/auth/me/")
async def get_current_user_info(current_user: UserAuth = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    user = users_db.get(current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user.id,
        "phone_number": user.phone_number,
        "created_at": user.created_at
    }