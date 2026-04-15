from abc import ABC, abstractmethod

class CleaningInterface(ABC):
    @abstractmethod
    def clean_text(self, text: str) -> str:
        """Sanitize and clean text content."""
        pass

    @abstractmethod
    def extract_structured_data(self, text: str) -> dict:
        """Extract structured person data from PDF content."""
        pass
