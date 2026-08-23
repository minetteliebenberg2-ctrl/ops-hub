# ==========================================================
# FC Hub - Document Text Reader
# ----------------------------------------------------------
# Purpose:
# Extract raw text from Word (.docx) and PDF (.pdf) files
# so it can be handed to SignatureFieldExtractor. Does not
# interpret the text - only reads it.
# ==========================================================

from pathlib import Path

import docx
from pypdf import PdfReader


class UnsupportedDocumentType(Exception):
    """Raised when the file extension is not supported."""


class DocumentTextReader:

    SUPPORTED_EXTENSIONS = (".docx", ".pdf")

    def read(self, file_path):

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        extension = path.suffix.lower()

        if extension == ".docx":
            return self._read_docx(path)

        if extension == ".pdf":
            return self._read_pdf(path)

        raise UnsupportedDocumentType(
            f"Unsupported document type: {extension}. "
            f"Supported types: {', '.join(self.SUPPORTED_EXTENSIONS)}"
        )

    # --------------------------------------------------

    def _read_docx(self, path):

        document = docx.Document(str(path))

        paragraphs = [paragraph.text for paragraph in document.paragraphs]

        return "\n".join(paragraphs)

    # --------------------------------------------------

    def _read_pdf(self, path):

        reader = PdfReader(str(path))

        pages = [page.extract_text() or "" for page in reader.pages]

        return "\n".join(pages)
