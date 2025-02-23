import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi import FastAPI, HTTPException, Depends
import asyncpg
from main import app, get_db
from pydantic import BaseModel

#test database
TEST_DB_CONFIG = {
    "user": "doc_user",
    "password": "doc123",
    "database": "doc_manager",
    "host": "127.0.0.1",
    "port": 5432
}

@pytest_asyncio.fixture(scope="function")
async def test_pool():
    pool = await asyncpg.create_pool(**TEST_DB_CONFIG)
    
    async with pool.acquire() as conn:
        await conn.execute('DROP TABLE IF EXISTS documents')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                embedding FLOAT8[] NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    app.dependency_overrides[get_db] = lambda: pool
    
    yield pool
    
    async with pool.acquire() as conn:
        await conn.execute('DROP TABLE IF EXISTS documents')
    await pool.close()
    app.dependency_overrides.pop(get_db, None)

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_health_check(test_pool, client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["test"] == 1

@pytest.mark.asyncio
async def test_ingest_document(test_pool, client):
    payload = {"id": "doc1", "content": "Sample content"}
    response = await client.post("/ingest", json=payload)
    assert response.status_code == 201
    assert response.json() == {"message": "Document ingested successfully", "id": "doc1"}
    
    async with test_pool.acquire() as conn:
        doc = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", "doc1")
        assert doc is not None
        assert doc["content"] == "Sample content"
        assert doc["embedding"] is not None

@pytest.mark.asyncio
async def test_ingest_duplicate_document(test_pool, client):
    payload = {"id": "doc2", "content": "Another sample content"}
    await client.post("/ingest", json=payload)
    
    response = await client.post("/ingest", json=payload)
    assert response.status_code == 400
    assert response.json() == {"detail": f"Document with id {payload['id']} already exists"}

@pytest.mark.asyncio
async def test_invalid_document_format(client, test_pool):
    payload = {"content": "Missing ID field"}
    response = await client.post("/ingest", json=payload)
    assert response.status_code == 422
    error_detail = response.json()["detail"]
    assert any("id" in str(error["loc"]) for error in error_detail)

@pytest.mark.asyncio
async def test_ask_question(test_pool, client):
    doc_payload = {"id": "doc6", "content": "FastAPI is a modern web framework"}
    ingest_response = await client.post("/ingest", json=doc_payload)
    assert ingest_response.status_code == 201, f"Document ingestion failed: {ingest_response.json()}"
    
    async with test_pool.acquire() as conn:
        doc = await conn.fetchrow("SELECT * FROM documents WHERE id = $1", "doc6")
        assert doc is not None, "Document not found in database"
        assert doc["content"] == "FastAPI is a modern web framework"
        assert doc["embedding"] is not None, "Document embedding is missing"
    
    question_payload = {
        "question": "What is FastAPI?",
        "document_ids": ["doc6"]
    }
    response = await client.post("/ask", json=question_payload)
    
    print(f"\nAsk endpoint response: {response.status_code}")
    print(f"Response body: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "document_id" in data
    assert "similarity_score" in data
    assert data["document_id"] == "doc6"
    assert data["answer"] == "FastAPI is a modern web framework"

@pytest.mark.asyncio
async def test_ask_question_no_documents(test_pool, client):
    question_payload = {
        "question": "Any documents?",
        "document_ids": ["nonexistent"]
    }
    response = await client.post("/ask", json=question_payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "No documents found"}

@pytest.mark.asyncio
async def test_get_document(test_pool, client):
    #ingest a document first
    payload = {"id": "doc3", "content": "Test document for retrieval"}
    await client.post("/ingest", json=payload)
    
   
    response = await client.get("/documents/doc3")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "doc3"
    assert data["content"] == "Test document for retrieval"
    assert "created_at" in data

@pytest.mark.asyncio
async def test_get_all_documents(test_pool, client):
    #ingest multiple documents
    await client.post("/ingest", json={"id": "doc4", "content": "First doc"})
    await client.post("/ingest", json={"id": "doc5", "content": "Second doc"})
    
    #retrieve all documents
    response = await client.get("/documents")
    assert response.status_code == 200
    documents = response.json()
    assert len(documents) == 2
    assert {doc["id"] for doc in documents} == {"doc4", "doc5"}