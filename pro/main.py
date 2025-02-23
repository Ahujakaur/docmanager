from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from pymongo.errors import DuplicateKeyError
from datetime import datetime
from contextlib import asynccontextmanager

#embedding model 
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

@asynccontextmanager
async def lifespan(app: FastAPI):
  
    global client
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    yield
   
    if client:
        client.close()

app = FastAPI(
    title="Document Q&A API",
    description="API for document ingestion and question answering using embeddings",
    version="1.0.0",
    lifespan=lifespan
)

class Document(BaseModel):
    id: str
    content: str

class Question(BaseModel):
    question: str
    document_ids: Optional[List[str]] = None

async def get_db():
    return client["documentdb"]["documents"]

@app.get("/", include_in_schema=False)
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

@app.post("/ingest", status_code=201)
async def ingest_document(doc: Document, collection=Depends(get_db)):
    try:
        embedding = embedding_model.encode(doc.content)
        result = await collection.insert_one({
            "_id": doc.id,
            "content": doc.content,
            "embedding": embedding.tolist(),
            "created_at": datetime.utcnow()
        })
        return {"message": "Document ingested successfully", "id": doc.id}
    except DuplicateKeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Document with id {doc.id} already exists"
        )

@app.post("/ask")
async def ask_question(question: Question, collection=Depends(get_db)):
    if not question.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    question_embedding = embedding_model.encode(question.question)
    
    query = {"_id": {"$in": question.document_ids}} if question.document_ids else {}
    documents = await collection.find(query).to_list(length=100)  # Limit to 100 docs
    
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found matching criteria")
    
    similarities = []
    for doc in documents:
        try:
            doc_embedding = np.array(doc['embedding'], dtype=np.float32)
            similarity = cosine_similarity([question_embedding], [doc_embedding])[0][0]
            similarities.append((doc['_id'], doc['content'], similarity))
        except KeyError:
            continue
    
    if not similarities:
        raise HTTPException(status_code=404, detail="No valid documents with embeddings found")
    
    similarities.sort(key=lambda x: x[2], reverse=True)
    top_doc_id, top_doc_content, similarity = similarities[0]
    
    return {
        "answer": f"Based on document {top_doc_id}: {top_doc_content[:200]}...",
        "document_id": top_doc_id,
        "similarity_score": round(float(similarity), 4)
    }

@app.post("/select-documents")
async def select_documents(document_ids: List[str]):
    if not document_ids:
        raise HTTPException(status_code=400, detail="At least one document ID required")
    return {"selected_document_ids": document_ids}