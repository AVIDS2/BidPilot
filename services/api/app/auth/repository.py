from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def create_user(db: Session, user: User) -> User:
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)
