"""File parsing utilities for Cecil AI.

Supports extracting text from various file formats including PDF, DOCX, TXT, etc.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any


def parse_pdf(file_path: Path) -> str:
    """Extract text content from a PDF file.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content
        
    Raises:
        ImportError: If pypdf is not installed
        FileNotFoundError: If file doesn't exist
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError(
            "pypdf is required for PDF parsing. Install it with: pip install pypdf"
        )
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    reader = PdfReader(str(file_path))
    text_parts: list[str] = []
    
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if text.strip():
            text_parts.append(f"--- Page {page_num} ---\n{text}")
    
    return "\n\n".join(text_parts)


def parse_text_file(file_path: Path) -> str:
    """Extract text from a plain text file.
    
    Args:
        file_path: Path to the text file
        
    Returns:
        File content as string
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    return file_path.read_text(encoding="utf-8")


def parse_file(file_path: str | Path) -> dict[str, Any]:
    """Parse a file and extract its text content.
    
    Automatically detects file type and uses appropriate parser.
    
    Args:
        file_path: Path to the file to parse
        
    Returns:
        Dictionary with file metadata and extracted text:
        {
            "path": str,
            "name": str,
            "type": str,
            "content": str,
            "page_count": int (for PDFs),
        }
        
    Raises:
        ValueError: If file type is not supported
        FileNotFoundError: If file doesn't exist
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Detect file type
    mime_type, _ = mimetypes.guess_type(str(path))
    suffix = path.suffix.lower()
    
    result: dict[str, Any] = {
        "path": str(path.absolute()),
        "name": path.name,
        "type": mime_type or "unknown",
        "content": "",
    }
    
    # Parse based on file type
    if suffix == ".pdf" or mime_type == "application/pdf":
        content = parse_pdf(path)
        result["content"] = content
        result["type"] = "application/pdf"
        # Count pages
        result["page_count"] = content.count("--- Page ")
        
    elif suffix in [".txt", ".md", ".log", ".json", ".csv", ".yaml", ".yml"]:
        result["content"] = parse_text_file(path)
        result["type"] = f"text/{suffix[1:]}"
        
    elif suffix in [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h"]:
        result["content"] = parse_text_file(path)
        result["type"] = f"code/{suffix[1:]}"
        
    else:
        raise ValueError(
            f"Unsupported file type: {suffix}. "
            f"Supported: .pdf, .txt, .md, .log, .json, .csv, .yaml, .py, .js, etc."
        )
    
    return result


def format_file_context(file_info: dict[str, Any]) -> str:
    """Format parsed file information for agent context.
    
    Args:
        file_info: Dictionary returned by parse_file()
        
    Returns:
        Formatted string for inclusion in agent prompts
    """
    lines = [
        "=" * 80,
        f"FILE: {file_info['name']}",
        f"PATH: {file_info['path']}",
        f"TYPE: {file_info['type']}",
    ]
    
    if "page_count" in file_info:
        lines.append(f"PAGES: {file_info['page_count']}")
    
    lines.extend([
        "=" * 80,
        "",
        file_info["content"],
        "",
        "=" * 80,
    ])
    
    return "\n".join(lines)
