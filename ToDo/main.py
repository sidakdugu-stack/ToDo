from typing import List, Optional
from uuid import UUID
from fastapi import FastAPI, Depends
from pydantic import BaseModel  # Добавлен импорт BaseModel

# Импортируем систему авторизации
from auth_system import (
    # Модели
    PhoneRequest, EmailRequest, PhoneCodeVerification, EmailCodeVerification,
    Token, UserAuth,
    # Функции
    get_current_user, request_sms_code, request_email_code,
    verify_phone_code, verify_email_code, logout, get_current_user_info, get_auth_stats
)

app = FastAPI(
    title="Simple TodoList",
    description="API для управления задачами. Версия 0.2 добавлена авторизация",
    version="0.2"
)


# Модели данных для Todo
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


# "База данных" задач в памяти
todos_db = {}


# 📱 Эндпоинты аутентификации по телефону
@app.post("/auth/phone/request-code/")
async def auth_request_sms_code(phone_request: PhoneRequest):
    """Запрос кода для входа по номеру телефона"""
    return await request_sms_code(phone_request)


@app.post("/auth/phone/verify-code/", response_model=Token)
async def auth_verify_phone_code(phone_verification: PhoneCodeVerification):
    """Верификация кода для входа по номеру телефона"""
    return await verify_phone_code(phone_verification)


# 📧 Эндпоинты аутентификации по email
@app.post("/auth/email/request-code/")
async def auth_request_email_code(email_request: EmailRequest):
    """Запрос кода для входа по email"""
    return await request_email_code(email_request)


@app.post("/auth/email/verify-code/", response_model=Token)
async def auth_verify_email_code(email_verification: EmailCodeVerification):
    """Верификация кода для входа по email"""
    return await verify_email_code(email_verification)


# 🔐 Общие эндпоинты аутентификации
@app.post("/auth/logout/")
async def auth_logout(current_user: UserAuth = Depends(get_current_user)):
    """Выход из системы"""
    return await logout(current_user)


@app.get("/auth/me/")
async def auth_get_current_user_info(current_user: UserAuth = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    return await get_current_user_info(current_user)


@app.get("/auth/stats/")
async def auth_get_stats():
    """Получить статистику по аутентификации"""
    return await get_auth_stats()


# Основные эндпоинты приложения
@app.get("/")
def root():
    return {
        "message": "TodoList API with Auth - используйте /docs для тестирования",
        "auth_endpoints": {
            "phone": {
                "request_code": "/auth/phone/request-code/",
                "verify_code": "/auth/phone/verify-code/"
            },
            "email": {
                "request_code": "/auth/email/request-code/",
                "verify_code": "/auth/email/verify-code/"
            },
            "common": {
                "logout": "/auth/logout/",
                "me": "/auth/me/",
                "stats": "/auth/stats/"
            }
        }
    }


@app.get("/todos/", response_model=List[TodoItem])
def get_all_todos(
        completed: Optional[bool] = None,
        current_user: UserAuth = Depends(get_current_user)
):
    user_todos = [todo for todo in todos_db.values() if todo.user_id == current_user.user_id]

    if completed is not None:
        user_todos = [todo for todo in user_todos if todo.completed == completed]

    return user_todos


@app.get("/todos/{todo_id}", response_model=TodoItem)
def get_todo(
        todo_id: UUID,
        current_user: UserAuth = Depends(get_current_user)
):
    if todo_id not in todos_db or todos_db[todo_id].user_id != current_user.user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Todo not found")
    return todos_db[todo_id]


@app.post("/todos/", response_model=TodoItem, status_code=201)
def create_todo(
        todo: TodoCreate,
        current_user: UserAuth = Depends(get_current_user)
):
    from uuid import uuid4
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


@app.put("/todos/{todo_id}", response_model=TodoItem)
def update_todo(
        todo_id: UUID,
        todo_update: TodoUpdate,
        current_user: UserAuth = Depends(get_current_user)
):
    if todo_id not in todos_db or todos_db[todo_id].user_id != current_user.user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Todo not found")

    existing_todo = todos_db[todo_id]
    update_data = todo_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing_todo, field, value)

    return existing_todo


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(
        todo_id: UUID,
        current_user: UserAuth = Depends(get_current_user)
):
    if todo_id not in todos_db or todos_db[todo_id].user_id != current_user.user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Todo not found")

    del todos_db[todo_id]
    return


@app.patch("/todos/{todo_id}/complete", response_model=TodoItem)
def complete_todo(
        todo_id: UUID,
        current_user: UserAuth = Depends(get_current_user)
):
    if todo_id not in todos_db or todos_db[todo_id].user_id != current_user.user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Todo not found")

    todos_db[todo_id].completed = True
    return todos_db[todo_id]


@app.post("/todos/init-sample/")
def init_sample_todos(current_user: UserAuth = Depends(get_current_user)):
    sample_todos = [
        {"title": "Изучить FastAPI", "description": "Пройти tutorial"},
        {"title": "Купить продукты", "description": "Молоко, хлеб, яйца"},
        {"title": "Сделать домашку", "completed": True},
        {"title": "Позвонить маме"},
    ]

    user_todo_ids = [todo_id for todo_id, todo in todos_db.items() if todo.user_id == current_user.user_id]
    for todo_id in user_todo_ids:
        del todos_db[todo_id]

    from uuid import uuid4
    for todo_data in sample_todos:
        todo_id = uuid4()
        todos_db[todo_id] = TodoItem(
            id=todo_id,
            user_id=current_user.user_id,
            **todo_data
        )

    return {"message": f"Создано {len(sample_todos)} тестовых задач"}

