from pydantic import BaseModel
import qdrant_client
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.core.schema import Document
from llama_index.core import (
    VectorStoreIndex,
    Settings
)

from llama_index.core.query_engine import CitationQueryEngine
from dataclasses import dataclass
import os
import yaml
from app.prompts import LLM_STRUCTURING_PROMPT
import re
from typing import List, Optional
import pymupdf4llm
from openai import OpenAI as OpenAIClient

# Load config
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(_CONFIG_PATH, "r") as _f:
    _CONFIG = yaml.safe_load(_f) or {}

EMBED_MODEL_NAME = (
    _CONFIG.get("embeddings", {}).get("model") or "text-embedding-3-small"
)
STRUCTURED_LLM_MODEL = (
    _CONFIG.get("llm", {}).get("structured_model") or "gpt-4o-mini"
)

key = os.environ['OPENAI_API_KEY']

@dataclass
class Citation:
    source: str
    text: str

class Output(BaseModel):
    query: str
    response: str
    citations: list[Citation]

class DocumentService:
    
    def __init__(self, pdf_path: str = "docs/laws.pdf"):
        self.pdf_path = pdf_path
    
    def create_documents(self) -> list[Document]:
        """
        Extract text from the PDF and create Document objects for each law section.
        """
        docs = []
        
        try:
            # Parse PDF into sections using markdown conversion
            sections = self._parse_law_sections(self.pdf_path)
            
            # Create Document objects for each section
            for i, section in enumerate(sections):
                if section.strip():  # Skip empty sections
                    doc = Document(
                        metadata={"Section": f"Law {i+1}", "source": "laws.pdf", "method": "markdown"},
                        text=section.strip()
                    )
                    docs.append(doc)
            
            return docs
            
        except Exception as e:
            print(f"Error processing PDF: {e}")
            # Return some example documents if PDF processing fails
            return [
                Document(
                    metadata={"Section": "Law 1", "source": "laws.pdf", "method": "markdown"},
                    text="Theft is punishable by hanging",
                ),
                Document(
                    metadata={"Section": "Law 2", "source": "laws.pdf", "method": "markdown"},
                    text="Tax evasion is punishable by banishment.",
                ),
            ]

    def split_markdown_sections(self, text):
        
        # This document uses bold numbered sections like **1.** **Peace** instead of # headers
        # Match only main sections like: **1.** **Peace** (ignore subsections like 4.1.)
        main_section_pattern = re.compile(r'^\*\*(\d+\.)\*\*\s+\*\*([^*]+)\*\*', re.MULTILINE)
        
        sections = []
        
        # Collect only main section matches in order
        matches = list(main_section_pattern.finditer(text))
        
        for i, match in enumerate(matches):
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if content:
                sections.append({
                    "heading": f"{match.group(1)} {match.group(2).strip()}",
                    "level": 1,
                    "content": content,
                })
        
        return sections
    
    def _parse_law_sections(self, pdf_path: str) -> list[str]:
        """
        Parse the PDF into individual law sections using markdown conversion.
        Uses pymupdf4llm to convert PDF to markdown first, then parses by sections.
        """
        
        # Convert PDF to markdown
        md_reader = pymupdf4llm.LlamaMarkdownReader()
        documents = md_reader.load_data(pdf_path)
        
        # Extract markdown text from documents
        if not documents:
            return []
        
        markdown_texts = [document.text for document in documents]
        markdown_text = "\n".join(markdown_texts)
        
        # Use the custom markdown section parser for this specific document format
        md_sections = self.split_markdown_sections(markdown_text)
        
        # Convert structured sections back to text sections
        sections = []
        for section in md_sections:
            # Combine heading and content
            full_section = f"{section['heading']}\n\n{section['content']}"
            sections.append(full_section.strip())
        
        # Filter out very short sections and limit total
        sections = [s for s in sections if len(s.strip()) > 30]  # Keep substantial content
        return sections

    def create_documents_llm_structured_from_markdown(self, batch_size: int = 15) -> list[Document]:
        """
        Use markdown-derived sections instead of raw text, and structure them via LLM in batches.
        Processes up to `batch_size` sections per LLM call and concatenates the results.
        """
        # Pydantic models for structured output
        class LegalSection(BaseModel):
            section_number: str
            title: str
            content: str
            children: Optional[List['LegalSection']] = None

        class LegalDocument(BaseModel):
            sections: List[LegalSection]

        LegalSection.model_rebuild()

        try:
            # 1) Load markdown sections (already headed text per section)
            md_sections_text: List[str] = self._parse_law_sections(self.pdf_path)
            if not md_sections_text:
                return []

            # 2) Batch into groups of `batch_size`
            batches: List[List[str]] = [
                md_sections_text[i : i + batch_size] for i in range(0, len(md_sections_text), batch_size)
            ]

            client = OpenAIClient(api_key=key)
            processed_docs: List[Document] = []

            for batch in batches:
                # Combine selected sections with clear separation to aid parsing
                combined_md = "\n\n".join(batch)
                prompt = LLM_STRUCTURING_PROMPT.format(content=combined_md)

                response = client.chat.completions.parse(
                    model=STRUCTURED_LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a legal document parser that extracts structured information from legal texts."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format=LegalDocument,
                    temperature=0.1,
                    max_tokens=4000,
                )

                structured_data = response.choices[0].message.parsed
                sections = structured_data.sections if structured_data else []

                 # Create a Document per returned section (children become their own docs),
                # using only the section's own content (no parent accumulation).
                def add_section_and_children(curr: LegalSection) -> List[Document]:
                    docs_local: List[Document] = []
                    section_title = f"{curr.section_number}. {curr.title}"
                    docs_local.append(
                        Document(
                            metadata={
                                "Section": section_title,
                                "source": "laws.pdf",
                                "method": "llm_structured_md",
                                "section_number": curr.section_number,
                                "title": curr.title,
                            },
                            text=f"{curr.content}".strip(),
                        )
                    )
                    if curr.children:
                        for child in curr.children:
                            docs_local.extend(add_section_and_children(child))
                    return docs_local

                for top in sections:
                    processed_docs.extend(add_section_and_children(top))

            return processed_docs

        except Exception as e:
            print(f"Error processing markdown with LLM structuring: {e}")
            return [
                Document(
                    metadata={"Section": "Law 1", "source": "laws.pdf", "method": "llm_structured_md"},
                    text="Theft is punishable by hanging",
                ),
                Document(
                    metadata={"Section": "Law 2", "source": "laws.pdf", "method": "llm_structured_md"},
                    text="Tax evasion is punishable by banishment.",
                ),
            ]

class QdrantService:
    def __init__(self, k: int = 2):
        self.index = None
        self.k = k
    
    def connect(self) -> None:
        Settings.embed_model = OpenAIEmbedding(api_key=key, model=EMBED_MODEL_NAME)
        Settings.llm = OpenAI(api_key=key, model=STRUCTURED_LLM_MODEL)

        client = qdrant_client.QdrantClient(location=":memory:")
        vstore = QdrantVectorStore(client=client, collection_name='temp')

        self.index = VectorStoreIndex.from_vector_store(
            vector_store=vstore, 
        )
        

    def load(self, docs = list[Document]):
        self.index.insert_nodes(docs)
    
    def query(self, query_str: str, similarity_top_k: int | None = None, citation_chunk_size: int = 512) -> Output:
        """
        Query the vector store and return results with citations.
        """
        try:
            # Create a citation query engine
            top_k_to_use = similarity_top_k if similarity_top_k is not None else self.k
            citation_query_engine = CitationQueryEngine.from_args(
                self.index,
                similarity_top_k=top_k_to_use,
                citation_chunk_size=citation_chunk_size,
            )
            
            # Execute the query
            response = citation_query_engine.query(query_str)
            
            # Extract citations from the response
            citations = []
            if hasattr(response, 'source_nodes'):
                for i, node in enumerate(response.source_nodes):
                    citation = Citation(
                        source=node.metadata.get("Section", f"Section {i+1}"),
                        text=node.text
                    )
                    citations.append(citation)
            
            # Create output object
            output = Output(
                query=query_str,
                response=str(response),
                citations=citations
            )
            
            return output
            
        except Exception as e:
            print(f"Error during query: {e}")
            # Return a fallback response
            fallback_citations = [
                Citation(
                    source="Error",
                    text="Unable to retrieve specific citations due to an error."
                )
            ]
            
            return Output(
                query=query_str,
                response=f"I apologize, but I encountered an error while processing your query: {str(e)}",
                citations=fallback_citations
            )
       

if __name__ == "__main__":
    # Example workflow
    doc_service = DocumentService() # implemented
    docs = doc_service.create_documents_llm_structured_from_markdown()
    print("Done loading docs")
    qdrant_service = QdrantService() # implemented
    qdrant_service.connect() # implemented
    print("Connected to Qdrant")

    qdrant_service.load(docs) # implemented
    print("Loaded docs into Qdrant")

    print("Querying Qdrant")
    result = qdrant_service.query("What happens if I steal?", similarity_top_k=3, citation_chunk_size=128) # NOW implemented
    print(result)
    print(result.response)
    for citation in result.citations:
        print(f"{citation.source=}")
        print(f"{citation.text=}")
        print("-" * 100)





