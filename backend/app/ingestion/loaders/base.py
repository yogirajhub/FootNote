from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class DocumentPage:
    """Represents a single page or logical unit of content."""
    content: str
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadedDocument:
    """Result of loading a document file."""
    pages: List[DocumentPage]
    total_pages: int
    format: str
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.content for p in self.pages if p.content.strip())


class DocumentLoader(ABC):
    """Abstract base class for all document format loaders."""

    @abstractmethod
    def load(self, file_path: str) -> LoadedDocument:
        """Load a document from the given file path."""
        ...

    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of supported file extensions (without dot)."""
        ...

    def can_load(self, extension: str) -> bool:
        return extension.lower() in [e.lower() for e in self.supported_extensions()]
