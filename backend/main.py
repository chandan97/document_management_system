import shutil
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from unstructured.partition.image import partition_image
from config.database import engine, Base, SessionLocal
from sqlalchemy.orm import Session
from pydantic import BaseModel
from tempfile import NamedTemporaryFile
from models.user import User
from models.document import Document
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from nlp import DocumentIndexer
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from config.init_db import init_db,close_db
from elasticsearch import Elasticsearch
from io import BytesIO
from fastapi.middleware.cors import CORSMiddleware
import boto3
from botocore.exceptions import NoCredentialsError
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'


load_dotenv()

# AWS S3 configuration
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")


# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)


Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database when the application starts
    init_db()  # Create tables and indices
    indexer.create_index()
    yield  # Yield control back to FastAPI
    close_db()

app = FastAPI(lifespan=lifespan)
indexer = DocumentIndexer()

es = Elasticsearch("http://localhost:9200")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Directory where files will be saved
UPLOAD_DIRECTORY = "uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

# Security configuration
SECRET_KEY = "chandan123"  # Replace with a strong secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

# Function to verify the password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Function to get a user by username
def get_user(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

# Function to create a token
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class QueryRequest(BaseModel):
    query: str

    






@app.post("/query/")
async def handle_query(request: QueryRequest):
    # Perform search in Elasticsearch
    response = es.search(index="documents", body={
        "query": {
            "multi_match": {
                "query": request.query,
                "fields": ["title", "description", "content"]
            }
        }
    })
    
    results = []
    relevant_docs = []  # This will hold the relevant documents for generating a response

    for hit in response['hits']['hits']:
        doc = {
            "id": hit["_id"],
            "title": hit["_source"].get("title", "No Title"),
            "description": hit["_source"].get("description", "No Description"),
            "content": hit["_source"].get("content", "No Content")
        }
        results.append(doc)
        relevant_docs.append(hit)  # Store the raw hit for generating a response

    # Call the generate_response function with the relevant documents and the user's query
    generated_answer = indexer.generate_response(relevant_docs, request.query)

    return {
        "generated_answer": generated_answer  # Include the generated answer in the response
    }

@app.post("/register")
async def register(user: UserCreate):
    db: Session = SessionLocal()

    # Check if user already exists
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Create new user with hashed password
    hashed_password = pwd_context.hash(user.password)
    new_user = User(username=user.username, email=user.email, password=user.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "username": new_user.username, "email": new_user.email}

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db: Session = SessionLocal()
    try:
        user = get_user(db, form_data.username)
        if not user or not verify_password(form_data.password, user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect username or password")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        db.close()

# Document upload endpoint
@app.post("/upload")
async def upload_document(
    title: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)  # Use the session dependency here
):
    # Ensure file is provided
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    # Check for existing document with the same title
    existing_document = db.query(Document).filter(Document.title == title).first()
    if existing_document:
        raise HTTPException(status_code=400, detail="Document with this title already exists.")

    file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)

     # Save the file to the uploads directory
    with open(file_path, "wb") as buffer:
         shutil.copyfileobj(file.file, buffer)
    # Create a unique filename for S3
    file_key = f"{title}/{file.filename}"

    # Upload the file to S3
    try:
        file.file.seek(0)
        s3_client.upload_fileobj(file.file, AWS_BUCKET_NAME, file_key)
    except NoCredentialsError:
        raise HTTPException(status_code=500, detail="AWS credentials not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file to S3: {str(e)}")

    # Create the S3 file URL
    file_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{file_key}"

    # Determine OCR language
    languages = ["en"]  # You can extend this based on your needs

    

    # Parse the document using Unstructured.io
    elements = []
    try:
        if file.filename.endswith('.pdf'):
            print("processing pdf", file_path)
            elements = partition_pdf(file_path)  # Use the in-memory file object
            if not elements:
                raise HTTPException(status_code=400, detail="No elements extracted from PDF.")
        elif file.filename.endswith('.docx'):
            elements = partition_docx(file_path)  # Use the in-memory file object
        elif file.filename.endswith(('.png', '.jpg', '.jpeg')):
            elements = partition_image(file_path)  # Use the in-memory file object
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

    # Extract text from the parsed elements
    text = "\n".join([element.text for element in elements if element.text])

    # Create a new Document entry in the database
    document = Document(
        title=title,
        description=description,
        file_path=file_url,  # Store S3 URL instead of local path
        content=text  # Store parsed content if needed
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    # Index the document in Elasticsearch
    try:
        es.index(index="documents", document={
            "title": title,
            "description": description,
            "content": text
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error indexing document in Elasticsearch: {str(e)}")

    return {"id": document.id, "title": document.title, "file_path": document.file_path}