import secrets
import re
import phonenumbers
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException

from auth.config import auth_config


def generate_code(length: int = 6) -> str:
    """Генерирует цифровой код"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(length)])


def validate_username(username: str) -> bool:
    """Валидация никнейма"""
    if len(username) < 3 or len(username) > 30:
        return False

    if not re.match(r'^[a-zA-Z0-9а-яА-Я_-]+$', username):
        return False

    if username.isdigit():
        return False

    return True


def validate_phone_number(phone: str) -> bool:
    """Надежная валидация номера телефона"""
    try:
        # Используем библиотеку phonenumbers для точной валидации
        parsed = phonenumbers.parse(phone, "RU")

        # Проверяем, что номер валидный и возможный
        is_valid = phonenumbers.is_valid_number(parsed)
        is_possible = phonenumbers.is_possible_number(parsed)

        # Дополнительная проверка на российские номера
        country_code = parsed.country_code
        national_number = parsed.national_number

        if country_code != 7:  # Россия
            return False

        # Проверяем длину национального номера
        if len(str(national_number)) not in [10]:
            return False

        return is_valid and is_possible

    except phonenumbers.NumberParseException:
        # Fallback для учебного проекта - базовая проверка
        cleaned = ''.join(filter(str.isdigit, phone))
        if len(cleaned) < 10:
            return False

        # Проверяем, что номер не состоит из одних нулей
        if cleaned.strip('0') == '':
            return False

        # Проверяем российский код
        if not cleaned.startswith(('7', '8', '+7')):
            return False

        return len(cleaned) >= 11  # Минимальная длина российского номера


def sanitize_phone_number(phone: str) -> str:
    """Очистка и нормализация номера телефона"""
    # Удаляем все нецифровые символы
    cleaned = ''.join(filter(str.isdigit, phone))

    # Нормализуем российские номера
    if cleaned.startswith('8'):
        cleaned = '7' + cleaned[1:]
    elif cleaned.startswith('+7'):
        cleaned = '7' + cleaned[2:]

    return cleaned


def create_jwt_token(user_id: str) -> str:
    """Создание JWT токена"""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(seconds=auth_config.token_expiry),
        "iat": datetime.utcnow(),
        "type": "access"
    }
    return jwt.encode(payload, auth_config.secret_key, algorithm=auth_config.algorithm)


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Верификация JWT токена"""
    try:
        payload = jwt.decode(
            token,
            auth_config.secret_key,
            algorithms=[auth_config.algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")