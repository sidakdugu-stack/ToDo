from typing import Optional, Dict, Any
from uuid import uuid4, UUID
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import secrets
import time
import httpx
import ssl


# Модели данных для аутентификации
class PhoneRequest(BaseModel):
    phone_number: str


class EmailRequest(BaseModel):
    email: EmailStr


class PhoneCodeVerification(BaseModel):
    phone_number: str
    code: str


class EmailCodeVerification(BaseModel):
    email: EmailStr
    code: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: UUID


class User(BaseModel):
    id: UUID
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    created_at: float


# Конфигурация SMS/Email API
SMS_API_BASE_URL = "https://msg.ovrx.ru/api"
SMS_ENDPOINT = "/auth-code/sms"
EMAIL_ENDPOINT = "/auth-code/email"

# "Базы данных" в памяти
users_db = {}
phone_codes_db = {}  # {phone_number: {"code": "123456", "expires_at": timestamp}}
email_codes_db = {}  # {email: {"code": "123456", "expires_at": timestamp}}
active_tokens = {}  # {token: user_id}

# Конфигурация
CODE_LENGTH = 6
CODE_EXPIRY = 300  # 5 минут в секундах

# Схема аутентификации для Swagger
security = HTTPBearer()


# Модель для зависимостей
class UserAuth:
    def _init_(self, user_id: UUID):
        self.user_id = user_id


# Функции для работы с аутентификацией
def generate_code() -> str:
    """Генерирует шестизначный код"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(CODE_LENGTH)])


async def send_sms_code(phone_number: str, code: str) -> bool:
    """Отправка SMS кода через внешний API"""
    try:
        sms_data = {
            "phone": phone_number,
            "code": code
        }

        url = f"{SMS_API_BASE_URL}{SMS_ENDPOINT}"
        print(f"📱 Отправка SMS на URL: {url}")
        print(f"📱 Данные: {sms_data}")

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with httpx.AsyncClient(
                timeout=30.0,
                verify=ssl_context
        ) as client:
            response = await client.post(
                url,
                json=sms_data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "TodoApp/1.1"
                }
            )

            print(f"📱 Ответ от SMS API: {response.status_code} - {response.text}")

            if response.status_code in [200, 201, 202]:
                print(f"✅ SMS успешно отправлено на {phone_number}")
                return True
            else:
                print(f"❌ Ошибка отправки SMS: {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Ошибка при отправке SMS: {e}")
        return False


async def send_email_code(email: str, code: str) -> bool:
    """Отправка кода на email через внешний API"""
    try:
        email_data = {
            "email": email,
            "code": code
        }

        url = f"{SMS_API_BASE_URL}{EMAIL_ENDPOINT}"
        print(f"📧 Отправка Email на URL: {url}")
        print(f"📧 Данные: {email_data}")

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with httpx.AsyncClient(
                timeout=30.0,
                verify=ssl_context
        ) as client:
            response = await client.post(
                url,
                json=email_data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "TodoApp/1.1"
                }
            )

            print(f"📧 Ответ от Email API: {response.status_code} - {response.text}")

            if response.status_code in [200, 201, 202]:
                print(f"✅ Email успешно отправлен на {email}")
                return True
            else:
                print(f"❌ Ошибка отправки Email: {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ Ошибка при отправке Email: {e}")
        return False


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


async def request_sms_code(phone_request: PhoneRequest) -> Dict[str, Any]:
    """Запрос кода для входа по номеру телефона"""
    phone_number = phone_request.phone_number

    # Валидация номера телефона
    if not phone_number or len(phone_number) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number"
        )

    # Очищаем номер телефона
    phone_number = ''.join(filter(str.isdigit, phone_number))

    # Проверяем, не запрашивали ли код недавно (анти-спам)
    if phone_number in phone_codes_db:
        existing_code = phone_codes_db[phone_number]
        time_passed = time.time() - (existing_code["expires_at"] - CODE_EXPIRY)
        if time_passed < 60:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting new code"
            )

    # Генерируем код
    code = generate_code()
    expires_at = time.time() + CODE_EXPIRY

    # Сохраняем код
    phone_codes_db[phone_number] = {
        "code": code,
        "expires_at": expires_at,
        "attempts": 0,
        "created_at": time.time()
    }

    # Показываем код для тестирования
    print(f"🔧 Код для {phone_number}: {code}")

    # Пробуем отправить SMS
    print(f"🔄 Отправка SMS...")
    sms_sent = await send_sms_code(phone_number, code)

    if sms_sent:
        return {
            "message": "Код подтверждения отправлен по SMS",
            "expires_in": CODE_EXPIRY,
            "phone_number": phone_number
        }
    else:
        return {
            "message": "SMS сервис временно недоступен. Используйте код ниже для тестирования.",
            "code": code,
            "expires_in": CODE_EXPIRY,
            "phone_number": phone_number,
            "debug": True
        }


async def request_email_code(email_request: EmailRequest) -> Dict[str, Any]:
    """Запрос кода для входа по email"""
    email = email_request.email

    # Проверяем, не запрашивали ли код недавно (анти-спам)
    if email in email_codes_db:
        existing_code = email_codes_db[email]
        time_passed = time.time() - (existing_code["expires_at"] - CODE_EXPIRY)
        if time_passed < 60:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting new code"
            )

    # Генерируем код
    code = generate_code()
    expires_at = time.time() + CODE_EXPIRY

    # Сохраняем код
    email_codes_db[email] = {
        "code": code,
        "expires_at": expires_at,
        "attempts": 0,
        "created_at": time.time()
    }

    # Показываем код для тестирования
    print(f"🔧 Код для {email}: {code}")

    # Пробуем отправить Email
    print(f"🔄 Отправка Email...")
    email_sent = await send_email_code(email, code)

    if email_sent:
        return {
            "message": "Код подтверждения отправлен на email",
            "expires_in": CODE_EXPIRY,
            "email": email
        }
    else:
        return {
            "message": "Email сервис временно недоступен. Используйте код ниже для тестирования.",
            "code": code,
            "expires_in": CODE_EXPIRY,
            "email": email,
            "debug": True
        }


async def verify_phone_code(phone_verification: PhoneCodeVerification) -> Token:
    """Верификация кода для входа по номеру телефона"""
    phone_number = phone_verification.phone_number
    code = phone_verification.code

    # Очищаем номер телефона
    phone_number = ''.join(filter(str.isdigit, phone_number))

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
        remaining_attempts = 3 - code_data["attempts"]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid code. {remaining_attempts} attempts remaining"
        )

    # Удаляем использованный код
    del phone_codes_db[phone_number]

    # Ищем пользователя по телефону
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
            email=None,
            created_at=time.time()
        )
        users_db[user_id] = user
        print(f"✅ Создан новый пользователь по телефону: {phone_number}")

    # Генерируем токен
    token = secrets.token_urlsafe(32)
    active_tokens[token] = user.id

    print(f"✅ Успешный вход по телефону: {phone_number}")

    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id
    )


async def verify_email_code(email_verification: EmailCodeVerification) -> Token:
    """Верификация кода для входа по email"""
    email = email_verification.email
    code = email_verification.code

    # Проверяем существование кода
    if email not in email_codes_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code not requested or expired"
        )

    code_data = email_codes_db[email]

    # Проверяем срок действия
    if time.time() > code_data["expires_at"]:
        del email_codes_db[email]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code expired"
        )

    # Проверяем код
    if code_data["code"] != code:
        code_data["attempts"] += 1
        if code_data["attempts"] >= 3:
            del email_codes_db[email]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many attempts, request new code"
            )
        remaining_attempts = 3 - code_data["attempts"]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid code. {remaining_attempts} attempts remaining"
        )

    # Удаляем использованный код
    del email_codes_db[email]

    # Ищем пользователя по email
    user = None
    for user_id, user_data in users_db.items():
        if user_data.email == email:
            user = user_data
            break

    if not user:
        # Создаем нового пользователя
        user_id = uuid4()
        user = User(
            id=user_id,
            phone_number=None,
            email=email,
            created_at=time.time()
        )
        users_db[user_id] = user
        print(f"✅ Создан новый пользователь по email: {email}")

    # Генерируем токен
    token = secrets.token_urlsafe(32)
    active_tokens[token] = user.id

    print(f"✅ Успешный вход по email: {email}")

    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id
    )


async def logout(current_user: UserAuth) -> Dict[str, str]:
    """Выход из системы"""
    tokens_to_remove = []
    for token, user_id in active_tokens.items():
        if user_id == current_user.user_id:
            tokens_to_remove.append(token)

    for token in tokens_to_remove:
        del active_tokens[token]

    return {"message": "Logged out successfully"}


async def get_current_user_info(current_user: UserAuth) -> Dict[str, Any]:
    """Получить информацию о текущем пользователе"""
    user = users_db.get(current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user.id,
        "phone_number": user.phone_number,
        "email": user.email,
        "created_at": user.created_at
    }


async def get_auth_stats() -> Dict[str, Any]:
    """Получить статистику по аутентификации"""
    return {
        "total_users": len(users_db),
        "phone_codes": len(phone_codes_db),
        "email_codes": len(email_codes_db),
        "active_tokens": len(active_tokens)
    }