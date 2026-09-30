from __future__ import annotations

from functools import wraps
from typing import Optional

from flask import g, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import SessionLocal
from .models import Company, User


def register_company(company_name: str, email: str, password: str) -> User:
    with SessionLocal() as db:
        existing = db.query(User).filter_by(email=email).first()
        if existing:
            raise ValueError("An account with that email already exists.")

        company = Company(name=company_name)
        db.add(company)
        db.flush()  # populate company.id

        user = User(
            company_id=company.id,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def authenticate(email: str, password: str) -> Optional[User]:
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            return user
        return None


def login_user(user: User):
    session["user_id"] = user.id
    session["company_id"] = user.company_id


def logout_user():
    session.clear()


def current_user() -> Optional[User]:
    user_id = session.get("user_id")
    if not user_id:
        return None
    with SessionLocal() as db:
        return db.get(User, user_id)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        g.company_id = session["company_id"]
        return view(*args, **kwargs)

    return wrapped
