# Standard library imports
from dataclasses import dataclass
from typing import List, Optional

# Third-party imports
from pydantic import BaseModel

@dataclass
class Citation:
    source: str
    text: str

class Output(BaseModel):
    query: str
    response: str
    citations: list[Citation]

class LegalSection(BaseModel):
    section_number: str
    title: str
    content: str
    children: Optional[List['LegalSection']] = None

class LegalDocument(BaseModel):
    sections: List[LegalSection]

class LegalSectionGeneral(BaseModel):
    section_number: str
    title: str
    content: str

class LegalDocumentGeneral(BaseModel):
    sections: List[LegalSectionGeneral]

# Rebuild the model to handle forward references
LegalSection.model_rebuild()
