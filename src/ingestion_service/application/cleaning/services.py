from src.ingestion_service.application.cleaning.domain.interfaces import CleaningInterface
import re

class PDFCleaningService(CleaningInterface):
    def clean_text(self, text: str) -> str:
        # TODO: Port logic from llm_service.py/clean_markdown_formatting
        pass

    def extract_structured_data(self, text: str) -> dict:
        # TODO: Implement person data extraction
        pass
