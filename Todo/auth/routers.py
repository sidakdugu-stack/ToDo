from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from auth.dependencies import get_current_user, UserAuth
from auth.services import AuthService, cleanup_expired_data
from auth.models import (
    PhoneRequest, EmailRequest, PhoneCodeVerification,
    EmailCodeVerification, UsernameUpdate, Token
)

router = APIRouter(prefix="/auth", tags=["authentication"])

# 📱 Эндпоинты аутентификации по телефону
@router.post("/phone/request-code/")
async def request_phone_code(
    phone_request: PhoneRequest,
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    return await auth_service.request_phone_code(phone_request)

@router.post("/phone/verify-code/", response_model=Token)
async def verify_phone_code(
    verification: PhoneCodeVerification,
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    return await auth_service.verify_phone_code(verification)

# 📧 Эндпоинты аутентификации по email
@router.post("/email/request-code/")
async def request_email_code(
    email_request: EmailRequest,
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    return await auth_service.request_email_code(email_request)

@router.post("/email/verify-code/", response_model=Token)
async def verify_email_code(
    verification: EmailCodeVerification,
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    return await auth_service.verify_email_code(verification)

# 👤 Эндпоинты для работы с профилем
@router.patch("/profile/username/")
async def update_username(
    username_update: UsernameUpdate,
    current_user: UserAuth = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновить никнейм пользователя"""
    auth_service = AuthService(db)
    return auth_service.update_username(current_user.user_id, username_update)

# 🔐 Общие эндпоинты аутентификации
@router.post("/logout/")
async def logout(
    current_user: UserAuth = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    return auth_service.logout(current_user.user_id)

@router.get("/me/")
async def get_current_user_info(
    current_user: UserAuth = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    auth_service = AuthService(db)
    return auth_service.get_user_info(current_user.user_id)

@router.get("/stats/")
async def get_stats(db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    return auth_service.get_auth_stats()

@router.post("/admin/cleanup/")
def cleanup_expired_data_endpoint(db: Session = Depends(get_db)):
    """Очистка устаревших токенов и кодов (для админа)"""
    cleanup_expired_data(db)
    return {"message": "Expired data cleaned up successfully"}