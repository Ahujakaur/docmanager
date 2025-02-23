import pytest
import pytest_asyncio
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI
from main import app, get_db
from pydantic import BaseModel

#test database
@pytest_asyncio.fixture
async def test_db():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    test_database = client["test_documentdb"]
    yield test_database["documents"]
    client.close()

async def override_get_db():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    test_database = client["test_documentdb"]
    try:
        yield test_database["documents"]
    finally:
        client.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Welcome to Document Q&A API",
        "endpoints": {
            "POST /ingest": "Ingest a new document",
            "POST /ask": "Ask a question about documents",
            "POST /select-documents": "Select specific documents for querying",
            "GET /docs": "OpenAPI documentation",
            "GET /redoc": "ReDoc documentation"
        }
    }

@pytest.mark.asyncio
async def test_ingest_document(test_db):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {"id": "doc1", "content": "Sample content"}
        response = await ac.post("/ingest", json=payload)
    assert response.status_code == 201
    assert response.json() == {"message": "Document ingested successfully", "id": "doc1"}
    
    # verify document 
    doc = await test_db.find_one({"_id": "doc1"})
    assert doc is not None
    assert doc["content"] == "Sample content"

@pytest.mark.asyncio
async def test_ingest_duplicate_document(test_db):
    # first insertion
    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {"id": "doc2", "content": "Another sample content"}
        response = await ac.post("/ingest", json=payload)
    assert response.status_code == 201

    # second insertion 
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/ingest", json=payload)
    assert response.status_code == 400
    assert response.json() == {"detail": "Document with id doc2 already exists"}

@pytest.mark.asyncio
async def test_ask_question(test_db):
   
    async with AsyncClient(app=app, base_url="http://test") as ac:
        doc_payload = {"id": "doc3", "content": "This is a test document about FastAPI testing."}
        await ac.post("/ingest", json=doc_payload)

        
        question_payload = {
            "question": "What is this document about?",
            "document_ids": ["doc3"]
        }
        response = await ac.post("/ask", json=question_payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "document_id" in data
    assert "similarity_score" in data

@pytest.mark.asyncio
async def test_ask_question_no_documents(test_db):
 
    await test_db.delete_many({})
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        question_payload = {
            "question": "Is there any document?",
            "document_ids": ["non_existent"]
        }
        response = await ac.post("/ask", json=question_payload)
    assert response.status_code == 404
    assert "No documents found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_select_documents():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = ["doc1", "doc2"]  
        response = await ac.post("/select-documents", json=payload)
    assert response.status_code == 200
    assert response.json() == {"selected_document_ids": ["doc1", "doc2"]}

@pytest.mark.asyncio
async def test_invalid_document_format():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {"content": "Missing ID field"}
        response = await ac.post("/ingest", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert "Welcome to Document Q&A API" in response.json()["message"]
