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
# Handles WhatsApp .txt export formats across locales and platforms.
#
#   Android / modern (dash separator, no brackets):
#     3/12/25, 14:32 - John Doe: Hey there!
#     12/03/2025, 2:32 PM - John Doe: Hey there!
#
#   iOS / EU locale (square brackets, dot or slash date separator):
#     [3/12/25, 14:32:05] John Doe: Hey there!
#     [31.10.2022, 1:39:11] Shelly🌸: Hey there!
#
# Date separator: [./] supports both '.' (EU/IL) and '/' (US/UK) formats.
# Year: \d{2,4} handles both 2-digit (25) and 4-digit (2025) years.
# Sender: [^\[\]:] allows Hebrew, emojis, and special chars; stops at the
#         first ':' that acts as the sender/message delimiter.
# BiDi note: WhatsApp text exports store characters in logical (Unicode)
#   order regardless of display direction. The regex operates on logical
#   codepoints, so Hebrew (RTL) and English (LTR) text mix without issues.
#   Files are always read as UTF-8 (see load_documents) to preserve all
#   Unicode characters including Hebrew, emojis, and RTL marks.
#
# We preserve the full timestamp + sender in the Document text so that
# the LLM can answer date-specific questions ("who talked to me on March 12?").

# Shared sub-patterns for readability
_DATE   = r"\d{1,2}[./]\d{1,2}[./]\d{2,4}"           # 31.10.2022 or 3/12/25
_TIME   = r"\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?"    # 1:39:11 or 2:32 PM
_BIDI   = r"[\u200e\u200f\u202a-\u202e]*"              # optional BiDi directional control chars
_SENDER = r"[^\[\]:\u200e\u200f\u202a-\u202e]+"        # Hebrew + emojis; excludes BiDi marks
_MSG    = r".+"                                         # rest of line

# Each entry is (compiled_pattern, time_first).
#   time_first=False → capture groups are (date, time, sender, msg)
#   time_first=True  → capture groups are (time, date, sender, msg)
_WA_PATTERNS = [
    # Android: "3/12/25, 14:32 - Sender: msg"
    (re.compile(
        rf"^({_DATE}),\s+({_TIME})\s+-\s+({_SENDER}):\s*{_BIDI}({_MSG})$",
        re.MULTILINE | re.UNICODE,
    ), False),
    # iOS / EU (date first): "[31.10.2022, 1:39:11] Shelly🌸: msg"
    (re.compile(
        rf"^\[({_DATE}),\s+({_TIME})\]\s*({_SENDER}):\s*{_BIDI}({_MSG})$",
        re.MULTILINE | re.UNICODE,
    ), False),
    # IL reversed (time first): "[12:42:00 ,1.11.2022] רונשלי 🖤💍: msg"
    (re.compile(
        rf"^\[({_TIME})\s*,\s*({_DATE})\]\s*({_SENDER}):\s*{_BIDI}({_MSG})$",
        re.MULTILINE | re.UNICODE,
    ), True),
]

# Minimum number of matching lines to classify a file as a WhatsApp export
_WA_MIN_MATCHES = 3


def _is_whatsapp_export(text: str) -> bool:
    """Return True if *text* looks like a WhatsApp export file."""
    for pattern, _ in _WA_PATTERNS:
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

    for pattern, time_first in _WA_PATTERNS:
        matches = pattern.findall(text)
        if len(matches) >= _WA_MIN_MATCHES:
            for m in matches:
                if time_first:
                    time_str, date_str, sender, message = m
                else:
                    date_str, time_str, sender, message = m
                sender = sender.strip()
                message = message.strip()

                # Normalise timestamp into a readable, sortable string
                timestamp = f"{date_str} {time_str}".strip()

                # The chunk text the LLM will read — structured so the embedding
                # captures date, sender, and message content for semantic search.
                chunk_text = (
                    f"Date: {date_str}\n"
                    f"Time: {time_str}\n"
                    f"Sender: {sender}\n"
                    f"Message: {message}"
                )

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
