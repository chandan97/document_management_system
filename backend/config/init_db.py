from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# Load environment variables from a .env file
load_dotenv()

# Get the database URL from the environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    # Import your models here to register them with Base
    from models.user import User  # Adjust the import path as necessary
    from models.document import Document  # Adjust the import path as necessary

    # Create all tables in the database
    Base.metadata.create_all(bind=engine)

def close_db():
    """Close the database connection."""
    engine.dispose() 