from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from models.document import Document  # Ensure this is your correct model import
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
openai_api_key = os.getenv("OPENAI_API_KEY")

if DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable not set.")

# Create SQLAlchemy engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_base():
    return Base

def fetch_documents_from_db():
    db = SessionLocal()  # Create a new session
    try:
        documents = db.query(Document).all()  # Fetch all documents
        if not documents:
            logging.warning("No documents found in the database.")
            return []

        # Convert fetched data into a list of dictionaries
        return [{'content': doc.content, 'metadata': {'title': doc.title, 'description': doc.description}} for doc in documents]
    
    except Exception as e:
        logging.error(f"Error fetching documents: {e}")
        return []
    
    finally:
        db.close()  # Ensure the session is closed