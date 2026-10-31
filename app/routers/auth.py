import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from ..db import get_db, utc_now
from ..deps import get_current_user
from ..schemas import Credentials, TokenOut, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"], "created_at": row["created_at"]}


def _token_response(user: sqlite3.Row) -> dict:
    return {"access_token": create_access_token(user["id"]), "user": _user_out(user)}


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: Credentials, db: sqlite3.Connection = Depends(get_db)):
    email = body.email.strip().lower()
    try:
        cur = db.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, hash_password(body.password), utc_now()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _token_response(user)


@router.post("/login", response_model=TokenOut)
def login(body: Credentials, db: sqlite3.Connection = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: sqlite3.Row = Depends(get_current_user)):
    return _user_out(user)
