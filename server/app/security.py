"""رمزنگاری گذرواژه (bcrypt مستقیم) و توکن JWT.

نکته: passlib با bcrypt>=4.1 ناسازگار است؛ برای همین از کتابخانه bcrypt
به‌صورت مستقیم استفاده می‌شود. هیچ کلید محرمانه‌ای در کد کاربر قرار نمی‌گیرد.
"""
import datetime
import bcrypt
from jose import jwt, JWTError
from .config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode()[:72], hashed.encode())
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": expire},
                      settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str):
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
