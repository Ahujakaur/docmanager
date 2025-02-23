from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg
from sentence_transformers import SentenceTransformer
from datetime import datetime
import logging
import numpy as np
from typing import List

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

app = FastAPI(
    title="Document Q&A API",
    description="API for document ingestion and question answering using embeddings",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


pg_pool = None

@app.on_event("startup")
async def startup():
    global pg_pool
    try:
        pg_pool = await asyncpg.create_pool(
            user='doc_user',
            password='doc123',
            database='doc_manager',
            host='127.0.0.1',
            port=5432,
            command_timeout=60
        )
        async with pg_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    embedding FLOAT8[],
                    created_at TIMESTAMP
                )
            ''')
            result = await conn.fetchval('SELECT 1')
            logger.info(f"Database connection test successful: {result}")
    except Exception as e:
        logger.error(f"Database connection error during startup: {str(e)}")
        pg_pool = None
        raise HTTPException(status_code=500, detail="Database connection not established")

@app.on_event("shutdown")
async def shutdown():
    global pg_pool
    if pg_pool:
        await pg_pool.close()
        pg_pool = None

async def get_db():
    if pg_pool is None:
        logger.error("Database connection not established")
        raise HTTPException(
            status_code=500,
            detail="Database connection not established"
        )
    return pg_pool

class Document(BaseModel):
    id: str
    content: str

class Question(BaseModel):
    question: str
    document_ids: List[str]

def cosine_similarity(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

@app.get("/health")
async def health_check(pool=Depends(get_db)):
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchval('SELECT 1')
            return {
                "status": "healthy",
                "database": "connected",
                "test": result
            }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.post("/ingest", status_code=201)
async def ingest_document(doc: Document, pool=Depends(get_db)):
    try:
        embedding = embedding_model.encode(doc.content)
        logger.debug(f"Generated embedding shape: {embedding.shape}")
        
        async with pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO documents(id, content, embedding, created_at)
                VALUES($1, $2, $3, $4)
            ''', doc.id, doc.content, embedding.tolist(), datetime.utcnow())
            
        return {"message": "Document ingested successfully", "id": doc.id}
    except asyncpg.exceptions.UniqueViolationError:
        raise HTTPException(
            status_code=400,
            detail=f"Document with id {doc.id} already exists"
        )
    except Exception as e:
        logger.error(f"Error ingesting document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error ingesting document: {str(e)}"
        )

@app.get("/documents/{doc_id}")
async def get_document(doc_id: str, pool=Depends(get_db)):
    try:
        async with pool.acquire() as conn:
            document = await conn.fetchrow('''
                SELECT id, content, created_at 
                FROM documents 
                WHERE id = $1
            ''', doc_id)
            
        if document is None:
            raise HTTPException(
                status_code=404,
                detail=f"Document with id {doc_id} not found"
            )
            
        return {
            "id": document['id'],
            "content": document['content'],
            "created_at": document['created_at']
        }
    except Exception as e:
        logger.error(f"Error retrieving document: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving document: {str(e)}"
        )

@app.get("/documents")
async def get_all_documents(pool=Depends(get_db)):
    try:
        async with pool.acquire() as conn:
            documents = await conn.fetch('''
                SELECT id, content, created_at 
                FROM documents
                ORDER BY created_at DESC
            ''')
            
        return [
            {
                "id": doc['id'],
                "content": doc['content'],
                "created_at": doc['created_at']
            }
            for doc in documents
        ]
    except Exception as e:
        logger.error(f"Error retrieving documents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving documents: {str(e)}"
        )

@app.post("/ask")
async def ask_question(question: Question, pool=Depends(get_db)):
    try:
        question_embedding = embedding_model.encode(question.question).tolist()
        
        async with pool.acquire() as conn:
            docs = await conn.fetch('''
                SELECT id, content, embedding
                FROM documents
                WHERE id = ANY($1)
            ''', question.document_ids)
            
            if not docs:
                raise HTTPException(status_code=404, detail="No documents found")
            
            # Find best matching document
            best_score = -1
            best_doc = None
            
            for doc in docs:
                score = cosine_similarity(
                    np.array(question_embedding),
                    np.array(doc['embedding'])
                )
                if score > best_score:
                    best_score = score
                    best_doc = doc
            
            return {
                "answer": best_doc['content'],
                "document_id": best_doc['id'],
                "similarity_score": best_score
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing question: {str(e)}"
        )