# Standard library imports
import os

# Third-party imports
import uvicorn
from fastapi import FastAPI, HTTPException, Query

# Local imports
from app.utils import DocumentService, Output, QdrantService

DOC_PATH = "docs/laws.pdf"

app = FastAPI(
    title="Norm AI Legal Query API",
    description="API for querying Game of Thrones laws using RAG pipeline",
    version="1.0.0"
)

# Global services - initialized on startup
doc_service = None
qdrant_service_llm_structured = None
qdrant_service_llm_structured_general = None
qdrant_service_markdown = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global doc_service, qdrant_service_llm_structured, qdrant_service_llm_structured_general, qdrant_service_markdown
    
    try:
        # Initialize document service
        doc_service = DocumentService()

        # Build index: LLM structured (from markdown in batches)
        docs_llm = doc_service.create_documents_llm_structured_from_markdown(batch_size=15, pdf_path=DOC_PATH)
        qdrant_service_llm_structured = QdrantService(k=3, collection_name="qdrant_service_llm_structured")
        qdrant_service_llm_structured.connect()
        qdrant_service_llm_structured.load(docs_llm)

        # Build index: LLM structured general (for different document formats)
        docs_llm_general = doc_service.create_documents_llm_structured_from_markdown_general(batch_size=1, pdf_path=DOC_PATH)
        qdrant_service_llm_structured_general = QdrantService(k=3, collection_name="qdrant_service_llm_structured_general")
        qdrant_service_llm_structured_general.connect()
        qdrant_service_llm_structured_general.load(docs_llm_general)

        # Build index: Markdown
        docs_markdown = doc_service.create_documents(pdf_path=DOC_PATH)
        qdrant_service_markdown = QdrantService(k=3, collection_name="qdrant_service_markdown")
        qdrant_service_markdown.connect()
        qdrant_service_markdown.load(docs_markdown)
        
        print(
            f"Loaded documents -> LLM: {len(docs_llm)}, LLM General: {len(docs_llm_general)}, Markdown: {len(docs_markdown)}"
        )
        
    except Exception as e:
        print(f"Error during startup: {e}")
        raise e

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Norm AI Legal Query API", 
        "docs": "/docs",
        "query_endpoints": {
            "llm_structured": "/query/llm_structured",
            "llm_structured_general": "/query/llm_structured_general",
            "markdown": "/query/markdown",
        },
    }

@app.get("/pdf-info")
async def get_pdf_info():
    """Get information about the loaded PDF document"""
    return {
        "pdf_path": DOC_PATH,
        "pdf_name": os.path.basename(DOC_PATH)
    }

@app.get("/query/llm_structured", response_model=Output)
async def query_llm_structured(
    q: str = Query(..., description="Query using LLM-structured documents"),
    similarity_top_k: int | None = Query(None, description="Top K results to retrieve"),
    citation_chunk_size: int = Query(512, description="Chunk size for citations"),
) -> Output:
    global qdrant_service_llm_structured
    if not qdrant_service_llm_structured:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        return qdrant_service_llm_structured.query(
            q,
            similarity_top_k=similarity_top_k,
            citation_chunk_size=citation_chunk_size,
        )
    except Exception as e:
        print(f"Error processing query (llm_structured): {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/query/llm_structured_general", response_model=Output)
async def query_llm_structured_general(
    q: str = Query(..., description="Query using LLM-structured general documents"),
    similarity_top_k: int | None = Query(None, description="Top K results to retrieve"),
    citation_chunk_size: int = Query(512, description="Chunk size for citations"),
) -> Output:
    global qdrant_service_llm_structured_general
    if not qdrant_service_llm_structured_general:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        return qdrant_service_llm_structured_general.query(
            q,
            similarity_top_k=similarity_top_k,
            citation_chunk_size=citation_chunk_size,
        )
    except Exception as e:
        print(f"Error processing query (llm_structured_general): {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/query/markdown", response_model=Output)
async def query_markdown(
    q: str = Query(..., description="Query using markdown-converted documents"),
    similarity_top_k: int | None = Query(None, description="Top K results to retrieve"),
    citation_chunk_size: int = Query(512, description="Chunk size for citations"),
) -> Output:
    global qdrant_service_markdown
    if not qdrant_service_markdown:
        raise HTTPException(status_code=503, detail="Service not initialized")
    try:
        return qdrant_service_markdown.query(
            q,
            similarity_top_k=similarity_top_k,
            citation_chunk_size=citation_chunk_size,
        )
    except Exception as e:
        print(f"Error processing query (markdown): {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "document_service": doc_service is not None,
            "llm_structured": qdrant_service_llm_structured is not None,
            "llm_structured_general": qdrant_service_llm_structured_general is not None,
            "markdown": qdrant_service_markdown is not None,
        }
    }

if __name__ == "__main__":
    # Run with: python app/main.py
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_flag = os.getenv("RELOAD", "false").lower() == "true"
    if reload_flag:
        uvicorn.run("app.main:app", host=host, port=port, reload=True)
    else:
        # Avoid double-import side effects in production
        uvicorn.run(app, host=host, port=port)