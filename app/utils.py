from passlib.context import CryptContext
from jose import jwt
import secrets
from datetime import datetime, timedelta

from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_EXPIRE_MINUTES = 60   
REFRESH_TOKEN_EXPIRE_DAYS = 7
SECRET_KEY = "432429b86e18123a3597bc62c56eee5108248d1ec68df9ae2f7fda456d329514"
ALGORITHM = "HS256"

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str):
    try:
        print(f"Verifying token: {token[:20]}...")  # Debug log
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"Token payload: {payload}")  # Debug log
        user_id = payload.get("sub")
        
        if user_id is None:
            print("No 'sub' found in token")  # Debug log
            return None
        
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            print(f"Invalid user_id format: {user_id}")  
            return None
        
        return {"user_id": user_id, "payload": payload}
        
    except jwt.JWTError as e:
        print(f"JWT Error: {e}")  
        return None
    
def authenticate_user(db, username: str, password: str):
    """
    Authenticate user by username and password
    """
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        return False
    
    if not verify_password(password, user.password):
        return False
    
    return user