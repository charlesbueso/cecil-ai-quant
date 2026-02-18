"""File parsing utilities for Cecil AI.

Supports extracting text from various file formats including PDF, DOCX, TXT, etc.
Also supports encoding images for multimodal vision processing.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

# Image extensions that should be processed via vision models
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# MIME types for image formats
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


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


def is_image_file(file_path: str | Path) -> bool:
    """Check if a file is an image based on its extension.
    
    Args:
        file_path: Path to check
        
    Returns:
        True if the file is a supported image format
    """
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS


def parse_image(file_path: str | Path) -> dict[str, Any]:
    """Encode an image file as base64 for multimodal vision processing.
    
    Args:
        file_path: Path to the image file
        
    Returns:
        Dictionary with image metadata and base64 data:
        {
            "path": str,
            "name": str,
            "type": str (MIME type),
            "is_image": True,
            "base64": str (base64-encoded image data),
            "data_url": str (data:image/...;base64,... URL),
        }
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a supported image format
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    suffix = path.suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise ValueError(f"Not a supported image format: {suffix}")
    
    mime_type = IMAGE_MIME_TYPES.get(suffix, "image/png")
    
    # Read and base64-encode the image
    image_bytes = path.read_bytes()
    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    
    return {
        "path": str(path.absolute()),
        "name": path.name,
        "type": mime_type,
        "is_image": True,
        "base64": b64_data,
        "data_url": f"data:{mime_type};base64,{b64_data}",
    }


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
    if suffix in IMAGE_EXTENSIONS:
        # Return image data for multimodal processing
        image_data = parse_image(path)
        result["type"] = image_data["type"]
        result["is_image"] = True
        result["base64"] = image_data["base64"]
        result["data_url"] = image_data["data_url"]
        result["content"] = f"[Image: {path.name}]"
    
    elif suffix == ".pdf" or mime_type == "application/pdf":
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
