from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Импортируем систему аутентификации и БД
from auth.routers import router as auth_router
from teams.routers import router as teams_router
from auth.dependencies import get_current_user, UserAuth
from database import get_db, Todo


# Middleware для проверки аутентификации
async def authentication_middleware(request: Request, call_next):
    # Пропускаем публичные эндпоинты
    public_paths = [
        "/docs", "/redoc", "/openapi.json",
        "/auth/phone/request-code", "/auth/phone/verify-code",
        "/auth/email/request-code", "/auth/email/verify-code",
        "/"
    ]

    # Проверяем точное соответствие для auth эндпоинтов
    if request.url.path in ["/docs", "/redoc", "/openapi.json", "/"]:
        response = await call_next(request)
        return response

    # Проверяем префиксы для auth
    if any(request.url.path.startswith(path) for path in [
        "/auth/phone/request-code",
        "/auth/phone/verify-code",
        "/auth/email/request-code",
        "/auth/email/verify-code"
    ]):
        response = await call_next(request)
        return response

    # Для защищенных эндпоинтов проверяем заголовок Authorization
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid authorization header"}
        )

    response = await call_next(request)
    return response


app = FastAPI(
    title="TodoList API",
    description="версия 0.5 с системой команд и улучшенной безопасностью",
    version="0.5"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Разрешенные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


# Добавляем middleware аутентификации
app.middleware("http")(authentication_middleware)

# Подключаем роутеры
app.include_router(auth_router)
app.include_router(teams_router)


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


class TodoCompletion(BaseModel):
    completed: bool


# 📋 Эндпоинты для работы с личными задачами
@app.get("/todos/", response_model=List[TodoItem])
def get_all_todos(
        completed: Optional[bool] = None,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Получить все личные задачи пользователя"""
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
    """Получить конкретную личную задачу"""
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
    """Создать новую личную задачу"""
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
    """Обновить личную задачу"""
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
    """Удалить личную задачу"""
    todo = db.query(Todo).filter(
        Todo.id == todo_id,
        Todo.user_id == current_user.user_id
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    db.delete(todo)
    db.commit()
    return


@app.patch("/todos/{todo_id}/completion", response_model=TodoItem)
def toggle_todo_completion(
        todo_id: str,
        completion: TodoCompletion,
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Отметить личную задачу как выполненную/невыполненную"""
    todo = db.query(Todo).filter(
        Todo.id == todo_id,
        Todo.user_id == current_user.user_id
    ).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    todo.completed = completion.completed
    db.commit()
    db.refresh(todo)
    return todo.to_dict()


@app.post("/todos/init-sample/")
def init_sample_todos(
        current_user: UserAuth = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Создать тестовые задачи для пользователя"""
    sample_todos = [
        {"title": "Изучить FastAPI", "description": "Пройти tutorial"},
        {"title": "Купить продукты", "description": "Молоко, хлеб, яйца"},
        {"title": "Сделать домашку", "completed": False},
        {"title": "Позвонить маме", "completed": False},
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
    """Корневой эндпоинт с информацией о API"""
    return {
        "message": "TodoList API with Teams System - используйте /docs для тестирования",
        "version": "0.5",
        "features": [
            "Authentication",
            "Database",
            "Usernames",
            "Personal Todos",
            "Team System",
            "Team Tasks",
            "Role Management",
            "Enhanced Security"
        ],
        "endpoints": {
            "auth": {
                "phone": ["/auth/phone/request-code/", "/auth/phone/verify-code/"],
                "email": ["/auth/email/request-code/", "/auth/email/verify-code/"],
                "profile": ["/auth/profile/username/", "/auth/me/", "/auth/logout/"]
            },
            "teams": {
                "management": ["/teams/", "/teams/{team_id}"],
                "members": ["/teams/{team_id}/members", "/teams/{team_id}/invite"],
                "tasks": ["/teams/{team_id}/tasks", "/teams/{team_id}/tasks/{task_id}"]
            },
            "todos": {
                "personal": ["/todos/", "/todos/{todo_id}", "/todos/init-sample/"]
            }
        }
    }


@app.get("/health")
def health_check():
    """Проверка здоровья API"""
    return {
        "status": "healthy",
        "version": "0.5",
        "service": "TodoList API"
    }


# Обработчик для несуществующих эндпоинтов
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def handle_unknown_path(path: str):
    """Обработчик для неизвестных эндпоинтов"""
    raise HTTPException(
        status_code=404,
        detail=f"Endpoint /{path} not found. Check /docs for available endpoints."
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)