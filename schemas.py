from pydantic import BaseModel, EmailStr, Field
from datetime import date
from typing import Optional

# Базова схема з спільними полями
class ContactBase(BaseModel):
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    email: EmailStr
    phone: str = Field(max_length=20)
    birthday: date
    additional_info: Optional[str] = None

# Схема для створення
class ContactCreate(ContactBase):
    pass

# Схема для оновлення
class ContactUpdate(ContactBase):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    birthday: Optional[date] = None

# Схема для відповіді (повертає ID)
class ContactResponse(ContactBase):
    id: int

    class Config:
        from_attributes = True # Дозволяє Pydantic читати дані з об'єктів SQLAlchemy

# Схеми для користувача
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)

class UserResponse(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True

# Схеми для аутентифікації
class TokenModel(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class LoginModel(BaseModel):
    email: EmailStr
    password: str