To use this README:

1. Create a new file named `README.md` in your project directory
2. Copy and paste the content above into the file
3. Update any placeholder values (like repository URL and license)

The README provides comprehensive documentation about:
- Project setup and installation
- Available endpoints and their usage
- Example API calls
- Project structure
- Dependencies
- Features

# Document Q&A API

A FastAPI-based REST API that provides document storage and question-answering capabilities using embeddings and semantic search.

## FastAPI Setup and Running Instructions

### 1. Environment Setup

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 2. MongoDB Setup

```bash
# Install MongoDB (Ubuntu/Debian)
sudo apt update
sudo apt install mongodb

# start MongoDB service
sudo systemctl start mongodb

# erify ongoDB is running
sudo systemctl status mongodb
```

### 3. Running the FastAPI Application

```bash
# Development server with auto-reload
uvicorn main:app --reload

# Production server
uvicorn main:app --host 0.0.0.0 --port 8000

# With specific host and port
uvicorn main:app --host 127.0.0.1 --port 8080

# With increased worker count (for production)
uvicorn main:app --workers 4
```

### 4. Available URLs After Starting Server

- API Root: http://localhost:8000/
- Interactive API documentation (Swagger UI): http://localhost:8000/docs
- Alternative API documentation (ReDoc): http://localhost:8000/redoc
- Health check: http://localhost:8000/health

### 5. Development Commands

```bash
# Install development dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest



### 6. Environment Variables (Optional)

Create a `.env` file in your project root:
```env
MONGODB_URL=mongodb://localhost:27017
DB_NAME=documentdb
COLLECTION_NAME=documents
PORT=8000
HOST=127.0.0.1
```

### 7. Debugging

- Enable debug logs:
```bash
uvicorn main:app --reload --log-level debug
```

- Common issues and solutions:
  - Port already in use: Change port using `--port XXXX`
  - MongoDB connection issues: Ensure MongoDB is running
  - Import errors: Verify all requirements are installed

## Postman Collection

You can import this Postman collection to test the API endpoints:

```json
{
    "info": {
        "name": "Document Q&A API",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "item": [
        {
            "name": "Root",
            "request": {
                "method": "GET",
                "url": {
                    "raw": "http://localhost:8000/"
                }
            }
        },
        {
            "name": "Ingest Document",
            "request": {
                "method": "POST",
                "header": [
                    {
                        "key": "Content-Type",
                        "value": "application/json"
                    }
                ],
                "url": {
                    "raw": "http://localhost:8000/ingest"
                },
                "body": {
                    "mode": "raw",
                    "raw": "{\n    \"id\": \"doc1\",\n    \"content\": \"FastAPI is a modern web framework for building APIs with Python.\"\n}"
                }
            }
        },
        {
            "name": "Ask Question",
            "request": {
                "method": "POST",
                "header": [
                    {
                        "key": "Content-Type",
                        "value": "application/json"
                    }
                ],
                "url": {
                    "raw": "http://localhost:8000/ask"
                },
                "body": {
                    "mode": "raw",
                    "raw": "{\n    \"question\": \"What is FastAPI?\",\n    \"document_ids\": [\"doc1\"]\n}"
                }
            }
        },
        {
            "name": "Select Documents",
            "request": {
                "method": "POST",
                "header": [
                    {
                        "key": "Content-Type",
                        "value": "application/json"
                    }
                ],
                "url": {
                    "raw": "http://localhost:8000/select-documents"
                },
                "body": {
                    "mode": "raw",
                    "raw": "{\n    \"document_ids\": [\"doc1\", \"doc2\"]\n}"
                }
            }
        }
    ]
}
```

### How to Use the Postman Collection

1. Open Postman
2. Click on "Import" button
3. Copy and paste the JSON above into the "Raw text" tab
4. Click "Continue" and then "Import"
5. You'll see a new collection named "Document Q&A API" with all the endpoints

### Test Sequence

1. Start your API server
2. Use the "Ingest Document" request to add some documents:
   ```json
   {
       "id": "doc1",
       "content": "FastAPI is a modern web framework for building APIs with Python."
   }
   ```
   ```json
   {
       "id": "doc2",
       "content": "MongoDB is a NoSQL database that stores data in flexible, JSON-like documents."
   }
   ```

3. Use the "Ask Question" request to query your documents:
   ```json
   {
       "question": "What is FastAPI?",
       "document_ids": ["doc1"]
   }
   ```

4. Use the "Select Documents" request to verify document existence:
   ```json
   {
       "document_ids": ["doc1", "doc2"]
   }
   ```

Let me know if you'd like to make any modifications to the README or if you need help with anything else!