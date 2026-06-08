from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
import os
import logging
import json
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="User Service", version="1.0.0")
security = HTTPBearer()
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET", "ai-cicd-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# In-memory DB for demo (replace with real PostgreSQL via SQLAlchemy)
users_db: dict = {}

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health")
def health():
    return {"status": "healthy", "service": "user-service", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/users/register", status_code=201)
def register(user: UserRegister):
    start = time.time()
    if user.username in users_db:
        raise HTTPException(status_code=400, detail="Username already exists")
    users_db[user.username] = {
        "username": user.username,
        "email": user.email,
        "password": hash_password(user.password),
        "created_at": datetime.utcnow().isoformat()
    }
    logger.info(json.dumps({"event": "user_registered", "username": user.username, "duration_ms": round((time.time()-start)*1000)}))
    return {"message": "User registered successfully", "username": user.username}

@app.post("/api/users/login", response_model=Token)
def login(credentials: UserLogin):
    start = time.time()
    user = users_db.get(credentials.username)
    if not user or not verify_password(credentials.password, user["password"]):
        logger.warning(json.dumps({"event": "login_failed", "username": credentials.username}))
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token({"sub": credentials.username, "email": user["email"]})
    logger.info(json.dumps({"event": "user_login", "username": credentials.username, "duration_ms": round((time.time()-start)*1000)}))
    return Token(access_token=token, token_type="bearer", username=credentials.username)

@app.get("/api/users/me")
def get_me(payload: dict = Depends(verify_token)):
    username = payload.get("sub")
    user = users_db.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": user["username"], "email": user["email"], "created_at": user["created_at"]}

@app.get("/api/users/{username}")
def get_user(username: str, payload: dict = Depends(verify_token)):
    user = users_db.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"username": user["username"], "email": user["email"]}
