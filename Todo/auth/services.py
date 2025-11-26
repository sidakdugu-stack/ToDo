import httpx
import ssl
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from database import get_db, User, VerificationCode, generate_default_username
from auth.config import auth_config
from auth.security import generate_code, validate_username, sanitize_phone_number, create_jwt_token
from auth.models import PhoneRequest, EmailRequest, PhoneCodeVerification, EmailCodeVerification, UsernameUpdate, Token


class SmsService:
    @staticmethod
    async def send_sms_code(phone: str, code: str) -> bool:
        """Отправка SMS кода через внешний API"""
        try:
            sms_data = {"phone": phone, "code": code}
            url = f"{auth_config.sms_api_base_url}{auth_config.sms_endpoint}"

            print(f"📱 Отправка SMS на URL: {url}")
            print(f"📱 Данные: {sms_data}")

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            async with httpx.AsyncClient(timeout=30.0, verify=ssl_context) as client:
                response = await client.post(
                    url,
                    json=sms_data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "TodoApp/1.1"
                    }
                )

                print(f"📱 Ответ от SMS API: {response.status_code} - {response.text}")
                return response.status_code in [200, 201, 202]

        except Exception as e:
            print(f"❌ Ошибка при отправке SMS: {e}")
            return False


class EmailService:
    @staticmethod
    async def send_email_code(email: str, code: str) -> bool:
        """Отправка кода на email через внешний API"""
        try:
            email_data = {"email": email, "code": code}
            url = f"{auth_config.sms_api_base_url}{auth_config.email_endpoint}"

            print(f"📧 Отправка Email на URL: {url}")
            print(f"📧 Данные: {email_data}")

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            async with httpx.AsyncClient(timeout=30.0, verify=ssl_context) as client:
                response = await client.post(
                    url,
                    json=email_data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "TodoApp/1.1"
                    }
                )

                print(f"📧 Ответ от Email API: {response.status_code} - {response.text}")
                return response.status_code in [200, 201, 202]

        except Exception as e:
            print(f"❌ Ошибка при отправке Email: {e}")
            return False


class CodeService:
    @staticmethod
    def create_verification_code(db: Session, phone: str = None, email: str = None) -> str:
        """Создание кода подтверждения"""
        from datetime import datetime, timedelta

        # Проверка анти-спам
        existing_code = db.query(VerificationCode).filter(
            (VerificationCode.phone_number == phone) | (VerificationCode.email == email),
            VerificationCode.expires_at > datetime.utcnow()
        ).first()

        if existing_code:
            time_passed = (datetime.utcnow() - existing_code.created_at).total_seconds()
            if time_passed < auth_config.request_cooldown:
                raise HTTPException(429, "Please wait before requesting new code")
            db.delete(existing_code)
            db.commit()

        # Создание нового кода
        code = generate_code(auth_config.code_length)
        expires_at = datetime.utcnow() + timedelta(seconds=auth_config.code_expiry)

        verification_code = VerificationCode(
            phone_number=phone,
            email=email,
            code=code,
            expires_at=expires_at
        )
        db.add(verification_code)
        db.commit()

        return code

    @staticmethod
    def verify_code(db: Session, phone: str = None, email: str = None, code: str = None):
        """Верификация кода"""
        verification_code = db.query(VerificationCode).filter(
            (VerificationCode.phone_number == phone) | (VerificationCode.email == email),
            VerificationCode.expires_at > datetime.utcnow()
        ).first()

        if not verification_code:
            raise HTTPException(400, "Code not requested or expired")

        if verification_code.code != code:
            verification_code.attempts += 1
            db.commit()

            if verification_code.attempts >= auth_config.max_attempts:
                db.delete(verification_code)
                db.commit()
                raise HTTPException(400, "Too many attempts, request new code")

            remaining = auth_config.max_attempts - verification_code.attempts
            raise HTTPException(400, f"Invalid code. {remaining} attempts remaining")

        # Удаляем использованный код
        db.delete(verification_code)
        db.commit()
        return True


class UserService:
    @staticmethod
    def get_or_create_user(db: Session, phone: str = None, email: str = None) -> User:
        """Получение или создание пользователя"""
        user = None

        if phone:
            user = db.query(User).filter(User.phone_number == phone).first()
        elif email:
            user = db.query(User).filter(User.email == email).first()

        if not user:
            username = generate_default_username(db)
            user = User(phone_number=phone, email=email, username=username)
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ Создан новый пользователь: {username}")

        return user

    @staticmethod
    def update_username(db: Session, user_id: str, new_username: str) -> Dict[str, Any]:
        """Обновление никнейма пользователя"""
        from auth.security import validate_username

        new_username = new_username.strip()

        # Валидация никнейма
        if not validate_username(new_username):
            raise HTTPException(
                status_code=400,
                detail="Username must be 3-30 characters long and can contain letters, numbers, underscores, and hyphens. Cannot be only numbers."
            )

        # Проверяем, не занят ли никнейм другим пользователем
        existing_user = db.query(User).filter(
            User.username == new_username,
            User.id != user_id
        ).first()

        if existing_user:
            raise HTTPException(400, "Username already taken")

        # Обновляем никнейм
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")

        old_username = user.username
        user.username = new_username
        db.commit()

        print(f"✅ Пользователь {user_id} сменил ник с '{old_username}' на '{new_username}'")

        return {
            "message": "Username updated successfully",
            "old_username": old_username,
            "new_username": new_username
        }


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.sms_service = SmsService()
        self.email_service = EmailService()
        self.code_service = CodeService()
        self.user_service = UserService()

    async def request_phone_code(self, phone_request: PhoneRequest) -> Dict[str, Any]:
        """Запрос кода для телефона"""
        phone_number = sanitize_phone_number(phone_request.phone_number)

        # Валидация номера телефона
        if not phone_number or len(phone_number) < 10:
            raise HTTPException(400, "Invalid phone number")

        code = self.code_service.create_verification_code(self.db, phone=phone_number)

        # Показываем код для тестирования
        print(f"🔧 Код для {phone_number}: {code}")

        # Пробуем отправить SMS
        sms_sent = await self.sms_service.send_sms_code(phone_number, code)

        if sms_sent:
            return {
                "message": "Код подтверждения отправлен по SMS",
                "expires_in": auth_config.code_expiry,
                "phone_number": phone_number
            }
        else:
            return {
                "message": "SMS сервис временно недоступен. Используйте код ниже для тестирования.",
                "code": code,
                "expires_in": auth_config.code_expiry,
                "phone_number": phone_number,
                "debug": True
            }

    async def request_email_code(self, email_request: EmailRequest) -> Dict[str, Any]:
        """Запрос кода для email"""
        email = email_request.email

        code = self.code_service.create_verification_code(self.db, email=email)

        print(f"🔧 Код для {email}: {code}")

        email_sent = await self.email_service.send_email_code(email, code)

        if email_sent:
            return {
                "message": "Код подтверждения отправлен на email",
                "expires_in": auth_config.code_expiry,
                "email": email
            }
        else:
            return {
                "message": "Email сервис временно недоступен. Используйте код ниже для тестирования.",
                "code": code,
                "expires_in": auth_config.code_expiry,
                "email": email,
                "debug": True
            }

    async def verify_phone_code(self, verification: PhoneCodeVerification) -> Token:
        """Верификация кода телефона"""
        phone_number = sanitize_phone_number(verification.phone_number)

        self.code_service.verify_code(
            self.db,
            phone=phone_number,
            code=verification.code
        )
        user = self.user_service.get_or_create_user(self.db, phone=phone_number)

        # Создаем JWT токен вместо случайной строки
        token = create_jwt_token(user.id)

        print(f"✅ Успешный вход по телефону: {phone_number} (ник: {user.username})")
        return Token(access_token=token, token_type="bearer", user_id=user.id)

    async def verify_email_code(self, verification: EmailCodeVerification) -> Token:
        """Верификация кода email"""
        self.code_service.verify_code(
            self.db,
            email=verification.email,
            code=verification.code
        )
        user = self.user_service.get_or_create_user(self.db, email=verification.email)

        # Создаем JWT токен вместо случайной строки
        token = create_jwt_token(user.id)

        print(f"✅ Успешный вход по email: {verification.email} (ник: {user.username})")
        return Token(access_token=token, token_type="bearer", user_id=user.id)

    def update_username(self, user_id: str, username_update: UsernameUpdate) -> Dict[str, Any]:
        """Обновление никнейма"""
        return self.user_service.update_username(self.db, user_id, username_update.username)

    def logout(self, user_id: str) -> Dict[str, str]:
        """Выход из системы - для JWT просто возвращаем сообщение"""
        # В JWT системе мы не храним токены, поэтому просто сообщаем об успехе
        return {"message": "Logged out successfully"}

    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Получить информацию о пользователе"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")

        return user.to_dict()

    def get_auth_stats(self) -> Dict[str, Any]:
        """Получить статистику по аутентификации"""
        total_users = self.db.query(User).count()

        # Для JWT мы не храним активные токены, поэтому возвращаем 0
        return {
            "total_users": total_users,
            "phone_codes": 0,  # Эти статистики больше не актуальны для JWT
            "email_codes": 0,
            "active_tokens": 0
        }


def cleanup_expired_data(db: Session):
    """Очистка устаревших кодов (токены больше не хранятся)"""
    now = datetime.utcnow()

    # Удаляем только просроченные коды
    expired_codes = db.query(VerificationCode).filter(VerificationCode.expires_at <= now).all()
    for code in expired_codes:
        db.delete(code)

    db.commit()
    print(f"✅ Очищено {len(expired_codes)} кодов")