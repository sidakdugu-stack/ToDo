from pydantic_settings import BaseSettings


class AuthConfig(BaseSettings):
    # SMS/Email API
    sms_api_base_url: str = "https://msg.ovrx.ru"
    sms_endpoint: str = "/auth-code/sms"
    email_endpoint: str = "/auth-code/email"

    # Security
    code_length: int = 6
    code_expiry: int = 300  # 5 minutes
    token_expiry: int = 24 * 60 * 60  # 24 hours
    max_attempts: int = 3
    request_cooldown: int = 60  # seconds

    # JWT Settings - ОЧЕНЬ ВАЖНО: сложный секретный ключ
    secret_key: str = "super-secret-jwt-key-2024-with-many-characters-and-symbols-@#$%^&*"
    algorithm: str = "HS256"

    class Config:
        env_file = ".env"


auth_config = AuthConfig()