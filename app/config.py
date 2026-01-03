from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # 数据库配置
    database_url: str
    redis_url: str
    
    # JWT配置
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # 应用配置
    debug: bool = False
    allowed_hosts: List[str] = ["*"]
    
    class Config:
        env_file = ".env"

settings = Settings()