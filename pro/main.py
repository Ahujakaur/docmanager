from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from pymongo.errors import DuplicateKeyError
from datetime import datetime

app = FastAPI(
    title="Document Q&A API",
    description="API for document ingestion and question answering using embeddings",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Document Q&A API",
        "endpoints": {
            "POST /ingest": "Ingest a new document",
            "POST /ask": "Ask a question about documents",
            "POST /select-documents": "Select specific documents for querying",
            "GET /docs": "OpenAPI documentation",
            "GET /redoc": "ReDoc documentation"
        }
    }

# Load a pre-trained embedding model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# MongoDB connection settings
MONGODB_URL = "mongodb://localhost:27017"
DB_NAME = "documentdb"
COLLECTION_NAME = "documents"
client = None
db = None

async def get_db():
    global client, db
    if client is None:
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client[DB_NAME]
    return db

class Document(BaseModel):
    id: str
    content: str

class Question(BaseModel):
    question: str
    document_ids: Optional[List[str]] = None

@app.on_event("startup")
async def startup():
    await get_db()

@app.on_event("shutdown")
async def shutdown():
    global client
    if client:
        client.close()

@app.post("/ingest")
async def ingest_document(doc: Document):
    db = await get_db()
    collection = db[COLLECTION_NAME]
    
    # Generate embeddings for the document content
    embedding = embedding_model.encode(doc.content)
    
    # Store the document and its embedding in MongoDB
    await collection.insert_one({
        "_id": doc.id,
        "content": doc.content,
        "embedding": embedding.tolist()
    })
    
    return {"message": "Document ingested successfully", "id": doc.id}

@app.post("/ask")
async def ask_question(question: Question):
    db = await get_db()
    collection = db[COLLECTION_NAME]
    
    # Generate embedding for the question
    question_embedding = embedding_model.encode(question.question)
    
    # Retrieve relevant documents
    query = {"_id": {"$in": question.document_ids}} if question.document_ids else {}
    documents = await collection.find(query).to_list(length=None)
    
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found")
    
    # Compute similarity between question and documents
    similarities = []
    for doc in documents:
        doc_embedding = np.array(doc['embedding'])
        similarity = cosine_similarity([question_embedding], [doc_embedding])[0][0]
        similarities.append((doc['_id'], doc['content'], similarity))
    
    # Sort by similarity and select the top document
    similarities.sort(key=lambda x: x[2], reverse=True)
    top_doc_id, top_doc_content, similarity = similarities[0]
    
    # Generate an answer using RAG (mock implementation)
    answer = f"Answer based on document {top_doc_id} (similarity: {similarity:.2f}): {top_doc_content[:100]}..."
    
    return {
        "answer": answer,
        "document_id": top_doc_id,
        "similarity_score": float(similarity)
    }

@app.post("/select-documents")
async def select_documents(document_ids: List[str]):
    return {"selected_document_ids": document_ids}