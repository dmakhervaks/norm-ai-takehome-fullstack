# Norm AI Legal Query Service

A RAG (Retrieval-Augmented Generation) pipeline for querying Game of Thrones laws using FastAPI, LlamaIndex, and Qdrant vector database.

## Overview

This service processes a PDF of laws from the fictional Game of Thrones universe, creates a vector store for semantic search, and provides a REST API to query the laws using natural language.

## Features

- **PDF Document Processing**: Automatically extracts and segments laws from the provided PDF
- **Vector Search**: Uses Qdrant in-memory vector database for similarity search
- **Citation Support**: Returns relevant citations with each query response
- **REST API**: FastAPI with automatic Swagger documentation
- **Docker Support**: Containerized application for easy deployment

## Architecture

```
docs/laws.pdf → DocumentService → QdrantService → FastAPI Endpoint
                     ↓              ↓               ↓
                 PDF parsing    Vector storage   Query interface
```

## Prerequisites

- Python 3.11+
- OpenAI API key
- Docker (optional)

## Setup and Installation

### Option 1: Local Development

1. **Clone the repository**:
   ```bash
   git clone <your-forked-repo-url>
   cd norm-ai-takehome-fullstack
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv norm-ai-venv
   source norm-ai-venv/bin/activate  # On Windows: norm-ai-venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install --index-url https://pypi.org/simple/ -r requirements.txt
   ```

4. **Set environment variables**:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```

5. **Run the application**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Option 2: Docker Deployment

1. **Build the Docker image**:
   ```bash
   docker build -t norm-ai-app .
   ```

2. **Run the container**:
   ```bash
   docker run --env-file .env -p 8000:80 norm-ai-app
   ```

### Environment (.env)

Create a `.env` file in the repo root to avoid passing secrets on the command line:

```bash
OPENAI_API_KEY=your-openai-api-key
```

Usage:
- With Docker: `docker run --env-file .env -p 8000:80 norm-ai-app`
- With Docker Compose: `docker compose up --build` (compose reads `.env` automatically)

### Frontend (Next.js)

Run the React UI that proxies to the backend:

```bash
cd frontend
pnpm install
BACKEND_HOST=localhost BACKEND_PORT=8000 pnpm dev
```

Then open http://localhost:3000

## Usage

### API Endpoints

Once the application is running, you can access:

- **Swagger Documentation**: http://localhost:8000/docs
- **API Root**: http://localhost:8000/
- **Health Check**: http://localhost:8000/health

### Query the Laws

Use the `/query` endpoint to ask questions about the Game of Thrones laws:

**Example Request**:
```bash
curl "http://localhost:8000/query?q=what%20happens%20if%20I%20steal%20from%20the%20Sept"
```

**Example Response**:
```json
{
  "query": "what happens if I steal from the Sept",
  "response": "According to the laws, theft from religious places like the Sept is considered a serious crime...",
  "citations": [
    {
      "source": "Law 15",
      "text": "Theft from the Sept or other holy places shall be punished by..."
    }
  ]
}
```

### Interactive API Documentation

Navigate to http://localhost:8000/docs to use the interactive Swagger interface:

1. Click on the `/query` endpoint
2. Click "Try it out"
3. Enter your question in the `q` parameter
4. Click "Execute"
5. View the structured response with citations

## Example Queries

Try these example queries:
- "What happens if I steal from the Sept?"
- "What are the punishments for murder?"
- "What laws govern marriage contracts?"
- "How should disputes between lords be resolved?"

## Implementation Details

### DocumentService
- Extracts text from `docs/laws.pdf` using PyMuPDF
- Intelligently segments the text into individual law sections
- Creates structured Document objects with metadata

### QdrantService
- Initializes in-memory Qdrant vector database
- Uses OpenAI embeddings for vector generation
- Implements CitationQueryEngine for response generation
- Returns top-k similar documents with citations

### FastAPI Application
- Startup event initializes services and loads documents
- Health check endpoint for monitoring
- Comprehensive error handling and logging
- Automatic request/response validation with Pydantic

## Dependencies

Key libraries used:
- `fastapi`: Web framework
- `llama-index`: RAG pipeline framework
- `qdrant-client`: Vector database client
- `PyMuPDF`: PDF text extraction
- `openai`: OpenAI API integration
- `pydantic`: Data validation

## Design Decisions

- **In-Memory Vector Store**: Uses Qdrant in-memory for simplicity and fast startup
- **Intelligent Text Segmentation**: Multiple parsing strategies to handle various law formats
- **Citation Support**: Maintains source tracking for transparency
- **Error Handling**: Graceful fallbacks when services fail
- **Containerization**: Docker support for consistent deployment
- PDF -> MD is better than PDF -> raw text as it helps break into main sections easier. Raw text worked decently with regex, but not as well as with MD parsing
- Usage of LLM was found to better structure text into more accurate sections/documents (but depending on document size, cost contraints, we would limit the amount of sections we parse at a time). The batch size, can be a function of the total tokens, but for now it is just constant.
- Initialization of query engine inside of query (to allow for dynamic k)
- We prepend the subtitles as part of the text
- We could spend more time with tuning the synthesizer templates (i.e. if we knew more of what the document distribution was like). However, we decided not to for the sake of this problem

## Assumptions
- The PDF will have some sort of list/hierachical nature
- There are headings, bolding, etc. which can be parsed into MD via helper libraries

### Common Issues

1. **OpenAI API Key Error**: Ensure your API key is set correctly
2. **Import Errors**: Make sure all dependencies are installed in the virtual environment
3. **Port Conflicts**: Change the port if 8000 is already in use
4. **PDF Not Found**: Ensure `docs/laws.pdf` exists in the correct location

### Logging

The application logs startup information and errors to the console. Check the logs if queries aren't working as expected.

