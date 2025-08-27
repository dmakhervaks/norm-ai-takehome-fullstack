from fastapi import FastAPI, Query, HTTPException
from app.utils import Output, DocumentService, QdrantService
import os
import gradio as gr
import uvicorn

app = FastAPI(
    title="Norm AI Legal Query API",
    description="API for querying Game of Thrones laws using RAG pipeline",
    version="1.0.0"
)

# Global services - initialized on startup
doc_service = None
qdrant_service_llm_structured = None
qdrant_service_markdown = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global doc_service, qdrant_service_llm_structured, qdrant_service_markdown
    
    try:
        # Initialize document service
        doc_service = DocumentService()

        # Build index: LLM structured (from markdown in batches)
        docs_llm = doc_service.create_documents_llm_structured_from_markdown(batch_size=15)
        qdrant_service_llm_structured = QdrantService(k=3)
        qdrant_service_llm_structured.connect()
        qdrant_service_llm_structured.load(docs_llm)

        # Build index: Markdown
        docs_markdown = doc_service.create_documents()
        qdrant_service_markdown = QdrantService(k=3)
        qdrant_service_markdown.connect()
        qdrant_service_markdown.load(docs_markdown)
        
        print(
            f"Loaded documents -> LLM: {len(docs_llm)}, Markdown: {len(docs_markdown)}"
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
        "gradio": "/gradio",
        "query_endpoints": {
            "llm_structured": "/query/llm_structured",
            "markdown": "/query/markdown",
        },
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
            "markdown": qdrant_service_markdown is not None,
        }
    }

# ------------------------
# Gradio UI
# ------------------------

SAMPLE_QUERIES = [
    "What happens if I steal?",
    "Who resolves disputes between petty lords vs. between great houses?",
    "Are holy men permitted to carry weapons under Maegor’s laws?",
    "What support and rights must heirs provide to a surviving widow?",
    "Is killing during a trial by combat considered murder?",
    "How are taxes collected, and what exception applies to the New Gift/Night’s Watch?",
]

def _gradio_query_fn(query: str, index_choice: str, similarity_top_k: int, citation_chunk_size: int) -> str:
    """
    Gradio handler that routes the query to the chosen index and formats a markdown response.
    """
    global qdrant_service_llm_structured, qdrant_service_markdown
    try:
        if index_choice == "llm_structured":
            if not qdrant_service_llm_structured:
                return "Service not initialized yet. Try again in a few seconds."
            result: Output = qdrant_service_llm_structured.query(
                query,
                similarity_top_k=similarity_top_k,
                citation_chunk_size=citation_chunk_size,
            )
        else:
            if not qdrant_service_markdown:
                return "Service not initialized yet. Try again in a few seconds."
            result: Output = qdrant_service_markdown.query(
                query,
                similarity_top_k=similarity_top_k,
                citation_chunk_size=citation_chunk_size,
            )

        citations_md = "\n\n".join([
            f"- **{c.source}**\n\n{c.text}" for c in (result.citations or [])
        ]) if getattr(result, "citations", None) else "No citations available."

        return f"**Answer**\n\n{result.response}\n\n**Citations**\n\n{citations_md}"
    except Exception as e:
        return f"Error processing query: {str(e)}"


demo = gr.Interface(
    fn=_gradio_query_fn,
    inputs=[
        gr.Textbox(label="Question", placeholder="Ask about the laws...", lines=2),
        gr.Radio(["llm_structured", "markdown"], value="llm_structured", label="Index"),
        gr.Number(value=3, label="Similarity Top K", precision=0),
        gr.Number(value=512, label="Citation Chunk Size", precision=0),
    ],
    outputs=gr.Markdown(label="Response"),
    title="Norm AI Legal Query",
    description="Query Game of Thrones law sections and see cited sources.",
    examples=[[q, "llm_structured", 3, 512] for q in SAMPLE_QUERIES],
)

demo.queue()

# Mount Gradio app at /gradio alongside FastAPI endpoints
app = gr.mount_gradio_app(app, demo, path="/gradio")

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