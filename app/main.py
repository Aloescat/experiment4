from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List

from . import crud, schemas, auth
from .database import get_db, get_redis
from .dependencies import get_current_active_user
from .config import settings

app = FastAPI(title="Auth Service", version="1.0.0")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_hosts,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    注册新用户
    """
    return crud.create_user(db=db, user=user)

@app.post("/login", response_model=schemas.Token)
def login(
    request: Request,
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    """
    用户登录，返回access和refresh tokens
    """
    # 验证用户
    db_user = crud.get_user_by_email(db, email=user.email)
    if not db_user or not auth.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    # 创建tokens
    access_token = auth.create_access_token(data={"sub": user.email})
    refresh_token = auth.create_refresh_token(data={"sub": user.email})
    
    # 记录登录历史
    user_agent = request.headers.get("User-Agent")
    crud.add_login_history(db=db, user_id=db_user.id, user_agent=user_agent)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@app.post("/refresh", response_model=schemas.Token)
def refresh_token(
    token_data: schemas.RefreshToken,
    redis=Depends(get_redis)
):
    """
    使用refresh token刷新access token
    """
    try:
        # 验证refresh token
        token_info = auth.verify_token(token_data.refresh_token, token_type="refresh")
        
        # 检查token是否在黑名单中
        if crud.is_token_blacklisted(redis, token_data.refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked"
            )
        
        # 创建新的access token
        access_token = auth.create_access_token(data={"sub": token_info.user_id})
        
        return {
            "access_token": access_token,
            "refresh_token": token_data.refresh_token,  # refresh token不变
            "token_type": "bearer"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@app.put("/user/update", response_model=schemas.User)
def update_user(
    user_update: schemas.UserUpdate,
    current_user: schemas.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新用户信息（email或密码）
    """
    return crud.update_user(db=db, user_id=current_user.id, user_update=user_update)

@app.get("/user/history", response_model=List[schemas.LoginHistoryItem])
def get_login_history(
    skip: int = 0,
    limit: int = 100,
    current_user: schemas.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取用户登录历史
    """
    history = crud.get_login_history(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    return history

@app.post("/logout")
def logout(
    request: Request,
    redis=Depends(get_redis),
    current_user: schemas.User = Depends(get_current_active_user)
):
    """
    用户登出，将token加入黑名单
    """
    auth_header = request.headers.get("Authorization")
    if auth_header:
        try:
            scheme, token = auth_header.split()
            if scheme.lower() == "bearer":
                # 解码token获取过期时间
                from jose import jwt
                payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
                exp_time = payload.get("exp")
                
                # 计算剩余时间
                from datetime import datetime
                current_time = datetime.utcnow().timestamp()
                expires_in = max(0, int(exp_time - current_time))
                
                # 将token加入黑名单
                crud.add_to_blacklist(redis, token, expires_in)
        except:
            pass
    
    return {"message": "Successfully logged out"}

@app.get("/health")
def health_check():
    """
    健康检查端点
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)