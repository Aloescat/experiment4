from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from . import crud, schemas, auth
from .database import get_db, get_redis
from .config import settings

async def get_current_user(
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    authorization: str = Header(None)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if authorization is None:
        raise credentials_exception
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise credentials_exception
        
        # 检查token是否在黑名单中
        if crud.is_token_blacklisted(redis, token):
            raise credentials_exception
        
        token_data = auth.verify_token(token)
    except (ValueError, JWTError):
        raise credentials_exception
    
    user = crud.get_user_by_email(db, email=token_data.user_id)
    if user is None:
        raise credentials_exception
    
    return user

async def get_current_active_user(current_user: schemas.User = Depends(get_current_user)):
    # 这里可以添加检查用户是否活跃的逻辑
    # 例如：if not current_user.is_active:
    #           raise HTTPException(status_code=400, detail="Inactive user")
    return current_user