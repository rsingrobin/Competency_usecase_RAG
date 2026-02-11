import uuid
from sqlalchemy import text
from app.db import SessionLocal
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAX_BCRYPT_BYTES = 72


def _truncate(password: str) -> bytes:
    pwd_bytes = password.encode("utf-8")
    return pwd_bytes[:MAX_BCRYPT_BYTES]

def hash_password(password: str) -> str:
    return pwd_context.hash(_truncate(password))

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(_truncate(password), hashed)

def login(email, password):
    session = SessionLocal()

    user = session.execute(text("""
        SELECT employee_id, password
        FROM employees
        WHERE email=:email
    """), {"email": email}).fetchone()

    if not user:
        return None

    m = user._mapping

    if not verify_password(password, m["password"]):
        return None

    token = str(uuid.uuid4())

    session.execute(text("""
        INSERT INTO employee_sessions(token, employee_id)
        VALUES(:t, :uid)
    """), {"t": token, "uid": m["employee_id"]})

    session.commit()
    session.close()

    return token


def get_employee(token):
    session = SessionLocal()

    row = session.execute(text("""
        SELECT employee_id
        FROM employee_sessions
        WHERE token=:t
    """), {"t": token}).fetchone()

    session.close()

    return row._mapping["employee_id"] if row else None

security = HTTPBearer()


def get_current_employee(
    credentials: HTTPAuthorizationCredentials = Depends(security),):
    token = credentials.credentials

    employee_id = get_employee(token)

    if not employee_id:
        raise HTTPException(401, "Invalid or expired session")

    return employee_id