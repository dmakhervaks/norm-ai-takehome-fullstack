# Standard library imports
import os
import re
from typing import List

# Third-party imports
import pymupdf4llm
import qdrant_client
import yaml
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.query_engine import CitationQueryEngine
from llama_index.core.schema import Document
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.qdrant import QdrantVectorStore
from openai import OpenAI as OpenAIClient

# Local imports
from app.contract import Citation, Output, LegalSection, LegalDocument, LegalDocumentGeneral
from app.prompts import LLM_STRUCTURING_PROMPT, LLM_STRUCTURING_PROMPT_GENERAL

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
TEMPERATURE = (
    _CONFIG.get("llm", {}).get("temperature") or 0.1
)
MAX_TOKENS = (
    _CONFIG.get("llm", {}).get("max_tokens") or 4000
)

key = os.environ['OPENAI_API_KEY']

def llm_request(messages: list, response_format, model: str = None, temperature: float = 0.1, max_tokens: int = 4000):
    """
    Make a structured LLM request with proper parameter handling for different model versions.
    """
    client = OpenAIClient(api_key=key)
    model = model or STRUCTURED_LLM_MODEL
    
    # Determine if we should use max_completion_tokens (newer models) or max_tokens (older models)
    # GPT-4o and newer models require max_completion_tokens
    request_params = {
        "model": model,
        "messages": messages,
        "response_format": response_format,
    }
    
    # For newer models (gpt-4o, gpt-4o-mini, o1, etc.), use max_completion_tokens
    if "o1" in model.lower() or "gpt-5" in model.lower():
        request_params["max_completion_tokens"] = max_tokens
    else:
        # For older models, use max_tokens
        request_params["max_tokens"] = max_tokens
        request_params["temperature"] = temperature

    return client.chat.completions.parse(**request_params)

class DocumentService:
    
    def create_documents(self, pdf_path: str = "docs/laws.pdf") -> list[Document]:
        """
        Extract text from the PDF and create Document objects for each law section.
        """
        docs = []
        
        try:
            # Parse PDF into sections using markdown conversion
            sections = self._parse_law_sections(pdf_path)
            
            # Create Document objects for each section
            for i, section in enumerate(sections):
                if section.strip():  # Skip empty sections
                    doc = Document(
                        metadata={"Section": f"Law {i+1}", "source": pdf_path, "method": "markdown"},
                        text=section.strip()
                    )
                    docs.append(doc)
            
            return docs
            
        except Exception as e:
            print(f"Error processing PDF: {e}")
            raise Exception(f"Error processing PDF: {e}")


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
                    "content": content,
                })
        
        return sections
    
    def _parse_law_sections(self, pdf_path: str) -> list[str]:
        """
        Parse the PDF into individual law sections using markdown conversion.
        Uses pymupdf4llm to convert PDF to markdown first, then parses by sections.
        """
        markdown_texts = self._load_pdf_to_markdown(pdf_path)
        if not markdown_texts:
            return []
            
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

    def _load_pdf_to_markdown(self, pdf_path: str) -> list[str]:
        """
        Convert PDF to markdown text sections.
        """
        md_reader = pymupdf4llm.LlamaMarkdownReader()
        documents = md_reader.load_data(pdf_path)
        
        if not documents:
            return []
        
        return [document.text for document in documents]

    def _parse_law_sections_general(self, pdf_path: str) -> list[str]:
        """
        Parse the PDF into individual law sections using markdown conversion.
        Uses pymupdf4llm to convert PDF to markdown first, then parses by sections.
        """
        markdown_texts = self._load_pdf_to_markdown(pdf_path)
        # Filter out very short sections and limit total
        sections = [s for s in markdown_texts if len(s.strip()) > 30]  # Keep substantial content
        return sections

    def _process_batch_with_llm(self, batch: List[str], prompt_template: str, response_format):
        """
        Process a batch of text sections through LLM structuring.
        """
        combined_md = "\n\n".join(batch)
        prompt = prompt_template.format(content=combined_md)

        messages = [
            {"role": "system", "content": "You are a legal document parser that extracts structured information from legal texts."},
            {"role": "user", "content": prompt},
        ]

        response = llm_request(
            messages=messages,
            response_format=response_format,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        structured_data = response.choices[0].message.parsed
        return structured_data.sections if structured_data else []


    def _batch_sections(self, sections: List[str], batch_size: int) -> List[List[str]]:
        """
        Split sections into batches of specified size.
        """
        return [sections[i : i + batch_size] for i in range(0, len(sections), batch_size)]

    def create_documents_llm_structured_from_markdown(self, batch_size: int = 15, pdf_path: str = "docs/laws.pdf") -> list[Document]:
        """
        Use markdown-derived sections instead of raw text, and structure them via LLM in batches.
        Processes up to `batch_size` sections per LLM call and concatenates the results.
        """
        try:
            # 1) Load markdown sections (already headed text per section)
            md_sections_text: List[str] = self._parse_law_sections(pdf_path)
            if not md_sections_text:
                return []

            # 2) Batch into groups of `batch_size`
            batches = self._batch_sections(md_sections_text, batch_size)

            processed_docs: List[Document] = []

            for batch in batches:
                sections = self._process_batch_with_llm(
                    batch, LLM_STRUCTURING_PROMPT, LegalDocument
                )

                # Create a Document per returned section (children become their own docs),
                # using only the section's own content (no parent accumulation).
                def add_section_and_children(curr: LegalSection) -> List[Document]:
                    docs_local: List[Document] = []
                    section_title = f"{curr.section_number}. {curr.title}"
                    docs_local.append(
                        Document(
                            metadata={
                                "Section": section_title,
                                "source": pdf_path,
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
            raise Exception(f"Error processing markdown with LLM structuring: {e}")

    def create_documents_llm_structured_from_markdown_general(self, batch_size: int = 1, pdf_path: str = "docs/laws.pdf") -> list[Document]:
        """
        Use markdown-derived sections for general PDF formats and structure them via LLM in batches.
        Processes up to `batch_size` sections per LLM call and concatenates the results.
        Uses the general parser for documents with different formats (like the dumb laws PDF).
        """

        try:
            # 1) Load markdown sections using general parser
            md_sections_text: List[str] = self._parse_law_sections_general(pdf_path)
            if not md_sections_text:
                return []

            # 2) Batch into groups of `batch_size`
            batches = self._batch_sections(md_sections_text, batch_size)

            processed_docs: List[Document] = []

            for batch in batches:
                sections = self._process_batch_with_llm(
                    batch, LLM_STRUCTURING_PROMPT_GENERAL, LegalDocumentGeneral
                )

                # Create a Document per returned section
                for section in sections:
                    section_title = f"{section.section_number}. {section.title}"
                    processed_docs.append(
                        Document(
                            metadata={
                                "Section": section_title,
                                "source": pdf_path,
                                "method": "llm_structured_md_general",
                                "section_number": section.section_number,
                                "title": section.title,
                            },
                            text=f"{section.content}".strip(),
                        )
                    )

            return processed_docs

        except Exception as e:
            print(f"Error processing markdown with LLM structuring (general): {e}")
            raise Exception(f"Error processing markdown with LLM structuring (general): {e}")

class QdrantService:
    def __init__(self, collection_name: str, k: int = 2):
        self.index = None
        self.collection_name = collection_name
        self.k = k
    
    def connect(self) -> None:
        Settings.embed_model = OpenAIEmbedding(api_key=key, model=EMBED_MODEL_NAME)
        Settings.llm = OpenAI(api_key=key, model=STRUCTURED_LLM_MODEL)

        client = qdrant_client.QdrantClient(location=":memory:")
        vstore = QdrantVectorStore(client=client, collection_name=self.collection_name)

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
    # docs = doc_service.create_documents_llm_structured_from_markdown()
    docs = doc_service.create_documents_llm_structured_from_markdown_general(pdf_path="docs/strange_state_laws.pdf")
    print("Done loading docs")
    qdrant_service = QdrantService(collection_name="temp") # implemented
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





