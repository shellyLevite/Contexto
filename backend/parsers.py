"""
parsers.py — Document loaders for PDF and WhatsApp exports.

Public API (used by ingest.py and main.py):

    from parsers import load_documents

    docs = load_documents(Path("data_export/chat.txt"))
    docs = load_documents(Path("data_export/resume.pdf"))

Each returned item is a llama_index.core.schema.Document.
"""

import logging
import re
from pathlib import Path

from llama_index.core.schema import Document

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp export parser
# ─────────────────────────────────────────────────────────────────────────────
# Handles the two most common WhatsApp .txt export formats:
#
#   Android / modern:
#     3/12/25, 14:32 - John Doe: Hey there!
#     12/03/2025, 2:32 PM - John Doe: Hey there!
#
#   iOS / old (square brackets):
#     [3/12/25, 14:32:05] John Doe: Hey there!
#
# We preserve the full timestamp + sender in the Document text so that
# the LLM can answer date-specific questions ("who talked to me on March 12?").

_WA_PATTERNS = [
    # Android: "3/12/25, 14:32 - Sender: msg"   or   "3/12/25, 2:32 PM - Sender: msg"
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s+"   # date
        r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)"  # time
        r"\s+-\s+"                             # separator
        r"([^:]+):\s+"                         # sender
        r"(.+)$",                              # message
        re.MULTILINE,
    ),
    # iOS: "[3/12/25, 14:32:05] Sender: msg"
    re.compile(
        r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s+"
        r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]"
        r"\s+([^:]+):\s+"
        r"(.+)$",
        re.MULTILINE,
    ),
]

# Minimum number of matching lines to classify a file as a WhatsApp export
_WA_MIN_MATCHES = 3


def _is_whatsapp_export(text: str) -> bool:
    """Return True if *text* looks like a WhatsApp export file."""
    for pattern in _WA_PATTERNS:
        if len(pattern.findall(text)) >= _WA_MIN_MATCHES:
            return True
    return False


def _parse_whatsapp(path: Path, text: str) -> list[Document]:
    """
    Parse a WhatsApp export into one Document per message.

    The timestamp and sender are embedded directly in the text content
    (e.g. "[2025-03-12 14:32] John Doe: Hey there!") so the RAG engine
    can answer date- and person-specific questions from the raw chunk text.
    They are also stored in metadata for potential future filtering.
    """
    docs: list[Document] = []

    for pattern in _WA_PATTERNS:
        matches = pattern.findall(text)
        if len(matches) >= _WA_MIN_MATCHES:
            for date_str, time_str, sender, message in matches:
                sender = sender.strip()
                message = message.strip()

                # Normalise timestamp into a readable, sortable string
                timestamp = f"{date_str} {time_str}".strip()

                # The chunk text the LLM will read — includes date + sender inline
                chunk_text = f"[{timestamp}] {sender}: {message}"

                docs.append(
                    Document(
                        text=chunk_text,
                        metadata={
                            "file_path": str(path),
                            "file_name": path.name,
                            "doc_type": "whatsapp",
                            "sender": sender,
                            "timestamp": timestamp,
                            "date": date_str,
                        },
                    )
                )
            logger.info(
                "WhatsApp parser: %d messages extracted from %s", len(docs), path.name
            )
            return docs

    # Fallback — shouldn't reach here if _is_whatsapp_export returned True
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# PDF parser (PyMuPDF)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_pdf(path: Path) -> list[Document]:
    """
    Extract text from a PDF using PyMuPDF, one Document per page.
    Pages with no extractable text are skipped.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is not installed. Run: pip install pymupdf"
        )

    docs: list[Document] = []
    pdf = fitz.open(str(path))

    for page_num, page in enumerate(pdf, start=1):
        text = page.get_text().strip()
        if not text:
            continue
        docs.append(
            Document(
                text=text,
                metadata={
                    "file_path": str(path),
                    "file_name": path.name,
                    "doc_type": "pdf",
                    "page": page_num,
                },
            )
        )

    pdf.close()
    logger.info("PDF parser: %d page(s) extracted from %s", len(docs), path.name)
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Generic fallback (SimpleDirectoryReader)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_generic(path: Path) -> list[Document]:
    """Load a plain .txt / .json / .csv file via LlamaIndex SimpleDirectoryReader."""
    from llama_index.core import SimpleDirectoryReader

    reader = SimpleDirectoryReader(input_files=[str(path)])
    docs = reader.load_data()
    logger.info("Generic parser: %d document(s) loaded from %s", len(docs), path.name)
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Public dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def load_documents(path: Path) -> list[Document]:
    """
    Return a list of LlamaIndex Documents for *path*.

    Routing rules:
      .pdf          → PyMuPDF (page-by-page)
      .txt with WA  → WhatsApp parser (message-by-message, timestamp preserved)
      everything else → SimpleDirectoryReader (generic)
    """
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _parse_pdf(path)

    if suffix == ".txt":
        text = path.read_text(encoding="utf-8", errors="replace")
        if _is_whatsapp_export(text):
            logger.info("Detected WhatsApp export: %s", path.name)
            return _parse_whatsapp(path, text)

    return _parse_generic(path)
