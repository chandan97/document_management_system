from sqlalchemy import Column, Integer, String
from config.init_db import Base
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)

    def __init__(self, username: str, email: str, password: str):
        self.username = username
        self.email = email
        self.password_hash = pwd_context.hash(password)  # Hash the password here


    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.password_hash)
