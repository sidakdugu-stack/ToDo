from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Импортируем систему авторизации и БД
from auth_system import (
    PhoneRequest, EmailRequest, PhoneCodeVerification, EmailCodeVerification,
    UsernameUpdate, Token, UserAuth, get_current_user, request_sms_code, request_email_code,
    verify_phone_code, verify_email_code, update_username, logout, get_current_user_info, get_auth_stats
)
from database import get_db, Todo

app = FastAPI(
    title="TodoList API",
    description="версия 0.3 с базой данных + ники",
    version="0.3"
)


# Модели данных для Todo
class TodoItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    completed: bool = False
    user_id: str


class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None


# 📱 Эндпоинты аутентификации по телефону
@app.post("/auth/phone/request-code/")
async def auth_request_sms_code(
        phone_request: PhoneRequest,
        db: Session = Depends(get_db)
):
    return await request_sms_code(phone_request, db)


@app.post("/auth/phone/verify-code/", response_model=Token)
async def auth_verify_phone_code(
        phone_verification: PhoneCodeVerification,
        db: Session = Depends(get_db)
):
    return await verify_phone_code(phone_verification, db)


# 📧 Эндпоинты аутентификации по email
@app.post("/auth/email/request-code/")
async def auth_request_email_code(
        email_request: EmailRequest,
        db: Session = Depends(get_db)
):
    return await request_email_code(email_request, db)


@app.post("/auth/email/verify-code/", response_model=Token)
async def auth_verify_email_code(
        email_verification: EmailCodeVerification,
        db: Session = Depends(get_db)
):
    return await verify_email_code(email_verification, db)


# 👤 Эндпоинты для работы с профилем
@app.patch("/auth/profile/username/")
async def auth_update_username(
        username_update: UsernameUpdate,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Обновить никнейм пользователя"""
    return await update_username(username_update, current_user, db)


# 🔐 Общие эндпоинты аутентификации
@app.post("/auth/logout/")
async def auth_logout(current_user: UserAuth = Depends(get_current_user)):
    return await logout(current_user)


@app.get("/auth/me/")
async def auth_get_current_user_info(
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    return await get_current_user_info(current_user, db)


@app.get("/auth/stats/")
async def auth_get_stats(db: Session = Depends(get_db)):
    return await get_auth_stats(db)


# 📋 Эндпоинты для работы с задачами
@app.get("/todos/", response_model=List[TodoItem])
def get_all_todos(
        completed: Optional[bool] = None,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    query = db.query(Todo).filter(Todo.user_id == current_user.user_id)

    if completed is not None:
        query = query.filter(Todo.completed == completed)

    todos = query.all()
    return [todo.to_dict() for todo in todos]


@app.get("/todos/{todo_id}", response_model=TodoItem)
def get_todo(
        todo_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    todo = db.query(Todo).filter(
        Todo.id == todo_id,
        Todo.user_id == current_user.user_id
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    return todo.to_dict()


@app.post("/todos/", response_model=TodoItem, status_code=201)
def create_todo(
        todo: TodoCreate,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    new_todo = Todo(
        title=todo.title,
        description=todo.description,
        user_id=current_user.user_id
    )
    db.add(new_todo)
    db.commit()
    db.refresh(new_todo)
    return new_todo.to_dict()


@app.put("/todos/{todo_id}", response_model=TodoItem)
def update_todo(
        todo_id: str,
        todo_update: TodoUpdate,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    todo = db.query(Todo).filter(
        Todo.id == todo_id,
        Todo.user_id == current_user.user_id
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    update_data = todo_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(todo, field, value)

    db.commit()
    db.refresh(todo)
    return todo.to_dict()


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(
        todo_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    todo = db.query(Todo).filter(
        Todo.id == todo_id,
        Todo.user_id == current_user.user_id
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    db.delete(todo)
    db.commit()
    return


@app.patch("/todos/{todo_id}/complete", response_model=TodoItem)
def complete_todo(
        todo_id: str,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    todo = db.query(Todo).filter(
        Todo.id == todo_id,
        Todo.user_id == current_user.user_id
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    todo.completed = True
    db.commit()
    db.refresh(todo)
    return todo.to_dict()


@app.post("/todos/init-sample/")
def init_sample_todos(
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    sample_todos = [
        {"title": "Изучить FastAPI", "description": "Пройти tutorial"},
        {"title": "Купить продукты", "description": "Молоко, хлеб, яйца"},
        {"title": "Сделать домашку", "completed": True},
        {"title": "Позвонить маме"},
    ]

    # Удаляем старые задачи пользователя
    db.query(Todo).filter(Todo.user_id == current_user.user_id).delete()

    # Создаем новые задачи
    for todo_data in sample_todos:
        todo = Todo(
            user_id=current_user.user_id,
            **todo_data
        )
        db.add(todo)

    db.commit()
    return {"message": f"Создано {len(sample_todos)} тестовых задач"}


@app.get("/")
def root():
    return {
        "message": "TodoList API with Usernames - используйте /docs для тестирования",
        "version": "0.3",
        "features": ["Authentication", "Database", "Usernames", "REST API"]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)