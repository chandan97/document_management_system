from sqlalchemy import Column, Integer, String, Text
from config.init_db import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    file_path = Column(String)
    content = Column(Text)  # New column to store parsed content