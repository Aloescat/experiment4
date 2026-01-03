from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from . import models, schemas, auth

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    # 检查用户是否已存在
    db_user = get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 创建新用户
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = user_update.model_dump(exclude_unset=True)
    
    if "password" in update_data:
        update_data["hashed_password"] = auth.get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    try:
        db.commit()
        db.refresh(db_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    return db_user

def add_login_history(db: Session, user_id: int, user_agent: Optional[str] = None):
    login_history = models.LoginHistory(
        user_id=user_id,
        user_agent=user_agent
    )
    db.add(login_history)
    db.commit()
    return login_history

def get_login_history(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(models.LoginHistory)
        .filter(models.LoginHistory.user_id == user_id)
        .order_by(models.LoginHistory.login_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def add_to_blacklist(redis, token: str, expires_in: int):
    """将token加入黑名单"""
    redis.setex(f"blacklist:{token}", expires_in, "true")

def is_token_blacklisted(redis, token: str) -> bool:
    """检查token是否在黑名单中"""
    return redis.exists(f"blacklist:{token}") == 1