from pydantic import BaseModel, EmailStr
from typing import Optional

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

class UsernameUpdate(BaseModel):
    username: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str

class UserResponse(BaseModel):
    id: str
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    username: str
    created_at: str

class AuthStats(BaseModel):
    total_users: int
    phone_codes: int
    email_codes: int
    active_tokens: int