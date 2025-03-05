"""Artifacts preview module for handling different file types and previews."""

# pylama:ignore=E501
import base64
import os
import mimetypes
import json
from pathlib import Path
from typing import Dict, Tuple, Optional, Union, List

# Initialize MIME types
mimetypes.init()


class ArtifactPreviewManager:
    """Manager class for handling artifact previews."""

    # Mapping of file extensions to preview types
    PREVIEW_TYPES = {
        # Code files
        ".py": "code",
        ".js": "code",
        ".jsx": "code",
        ".ts": "code",
        ".tsx": "code",
        ".html": "code",
        ".css": "code",
        ".json": "code",
        ".yaml": "code",
        ".yml": "code",
        ".xml": "code",
        ".md": "markdown",
        ".txt": "text",
        # Image files
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".gif": "image",
        ".svg": "image",
        ".webp": "image",
        # PDF
        ".pdf": "pdf",
        # Unsupported but displayable
        ".csv": "table",
        ".tsv": "table",
    }

    # Mapping file extensions to CodeMirror modes
    CODEMIRROR_MODES = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "jsx",
        ".ts": "javascript",
        ".tsx": "jsx",
        ".html": "htmlmixed",
        ".css": "css",
        ".json": "application/json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".xml": "xml",
        ".md": "markdown",
        ".java": "text/x-java",
        ".c": "text/x-csrc",
        ".cpp": "text/x-c++src",
        ".h": "text/x-csrc",
        ".cs": "text/x-csharp",
        ".rb": "ruby",
        ".go": "go",
        ".php": "php",
        ".sh": "shell",
        ".bash": "shell",
        ".sql": "sql",
        ".r": "r",
        ".lua": "lua",
        ".swift": "swift",
        ".dart": "dart",
        ".rs": "rust",
        ".kt": "kotlin",
        ".scala": "scala",
    }

    # Define binary file extensions for raw display
    BINARY_EXTENSIONS = {
        # Images
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico",
        # Documents
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        # Archives
        ".zip", ".tar", ".gz", ".rar", ".7z",
        # Media
        ".mp3", ".mp4", ".avi", ".mov", ".wav",
        # Other binaries
        ".db", ".sqlite", ".class", ".o", ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin"
    }

    def __init__(self, workspace_root: str):
        """Initialize the ArtifactPreviewManager.
        
        Args:
            workspace_root: Root directory for workspaces
        """
        self.workspace_root = workspace_root
        self.max_text_size = 10 * 1024 * 1024  # 10MB max for text files
        self.max_binary_size = 20 * 1024 * 1024  # 20MB max for binary files
        
    def get_artifact_preview(self, workspace_id: str, file_path: str) -> Dict:
        """Get preview information for an artifact.
        
        Args:
            workspace_id: ID of the workspace
            file_path: Path to the file relative to the workspace
            
        Returns:
            Dictionary with preview information including:
            - preview_type: Type of preview (code, image, pdf, etc.)
            - content: Content for the preview
            - meta: Additional metadata for the preview
        """
        # Construct the full path to the file
        full_path = os.path.join(self.workspace_root, workspace_id, file_path)
        
        # Check if the file exists
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return {
                "preview_type": "error",
                "error": "File not found",
                "path": file_path
            }
        
        # Check file size
        file_size = os.path.getsize(full_path)
        is_binary = self._is_binary_file(full_path)
        max_size = self.max_binary_size if is_binary else self.max_text_size
        
        if file_size > max_size:
            return {
                "preview_type": "error",
                "error": f"File too large to preview ({self._format_size(file_size)})",
                "path": file_path,
                "size": self._format_size(file_size)
            }
        
        # Determine the preview type
        preview_type, content, meta = self._get_preview_content(full_path, file_path)
        
        return {
            "preview_type": preview_type,
            "content": content,
            "meta": meta,
            "path": file_path,
            "size": self._format_size(file_size)
        }
    
    def _get_preview_content(self, full_path: str, file_path: str) -> Tuple[str, Union[str, bytes], Dict]:
        """Get the content for a preview based on the file type.
        
        Args:
            full_path: Full path to the file
            file_path: Path to the file relative to the workspace
            
        Returns:
            Tuple of (preview_type, content, metadata)
        """
        _, file_ext = os.path.splitext(file_path.lower())
        
        # Default metadata
        meta = {
            "filename": os.path.basename(file_path),
            "extension": file_ext
        }
        
        # Determine the preview type based on extension
        preview_type = self.PREVIEW_TYPES.get(file_ext, "unknown")
        
        if preview_type == "code" or preview_type == "text" or preview_type == "markdown":
            # For text-based files
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Add CodeMirror mode for code files
                if file_ext in self.CODEMIRROR_MODES:
                    meta["mode"] = self.CODEMIRROR_MODES[file_ext]
                    
                return preview_type, content, meta
            except UnicodeDecodeError:
                # If we can't decode as UTF-8, it might be binary
                return "binary", self._get_binary_preview(full_path), meta
                
        elif preview_type == "image":
            # For image files, return base64 encoded data
            try:
                with open(full_path, 'rb') as f:
                    image_data = f.read()
                
                mime_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
                data_uri = f"data:{mime_type};base64,{base64.b64encode(image_data).decode('ascii')}"
                
                meta["mime_type"] = mime_type
                return "image", data_uri, meta
                
            except Exception as e:
                return "error", str(e), meta
                
        elif preview_type == "pdf":
            # For PDFs, return a data URI
            try:
                with open(full_path, 'rb') as f:
                    pdf_data = f.read()
                
                data_uri = f"data:application/pdf;base64,{base64.b64encode(pdf_data).decode('ascii')}"
                return "pdf", data_uri, meta
                
            except Exception as e:
                return "error", str(e), meta
                
        elif preview_type == "table":
            # For CSV/TSV files
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Add delimiter info for table rendering
                meta["delimiter"] = "," if file_ext == ".csv" else "\t"
                return "table", content, meta
                
            except UnicodeDecodeError:
                return "binary", self._get_binary_preview(full_path), meta
        
        else:
            # Try to read as text first
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # If we get here, it's readable as text
                return "text", content, meta
                
            except UnicodeDecodeError:
                # If we can't decode as UTF-8, treat as binary
                return "binary", self._get_binary_preview(full_path), meta
    
    def _get_binary_preview(self, full_path: str) -> str:
        """Create a hex dump preview for binary files.
        
        Args:
            full_path: Full path to the file
            
        Returns:
            Hex dump as a string
        """
        try:
            # Read only the first 4KB for the hex dump
            with open(full_path, 'rb') as f:
                data = f.read(4096)
            
            # Create a hex dump
            hex_dump = []
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                # Hex values
                hex_line = ' '.join(f'{b:02x}' for b in chunk)
                # ASCII representation (printable chars only)
                ascii_line = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                
                # Format address, hex values, and ASCII
                line = f"{i:08x}:  {hex_line:<47}  |{ascii_line}|"
                hex_dump.append(line)
            
            if len(data) == 4096:
                hex_dump.append("... (truncated)")
                
            return '\n'.join(hex_dump)
            
        except Exception as e:
            return f"Error reading binary file: {str(e)}"
            
    def _is_binary_file(self, file_path: str) -> bool:
        """Check if a file is likely to be binary.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file appears to be binary, False otherwise
        """
        # Check extension first
        _, ext = os.path.splitext(file_path.lower())
        if ext in self.BINARY_EXTENSIONS:
            return True
        
        # Check file signature (magic bytes)
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)  # Read first 1KB to detect binary content
                
                # Look for null bytes or other non-text characters
                if b'\x00' in chunk:
                    return True
                
                # Check for high rate of non-ASCII characters
                non_ascii = sum(1 for b in chunk if b < 32 and b not in (9, 10, 13))  # tab, LF, CR
                if non_ascii > 0.3 * len(chunk):
                    return True
                    
                return False
                
        except Exception:
            # In case of error, assume it's binary for safety
            return True
            
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in a human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024 or unit == 'TB':
                return f"{size_bytes:.2f} {unit}".rstrip('0').rstrip('.') + ' ' + unit
            size_bytes /= 1024

    def get_artifacts_list(self, workspace_id: str, directory: str = "") -> List[Dict]:
        """Get a list of artifacts in a directory.
        
        Args:
            workspace_id: ID of the workspace
            directory: Directory path relative to the workspace
            
        Returns:
            List of dictionaries with artifact info
        """
        # Construct the full path to the directory
        full_dir_path = os.path.join(self.workspace_root, workspace_id, directory)
        
        if not os.path.exists(full_dir_path) or not os.path.isdir(full_dir_path):
            return []
        
        artifacts = []
        for item in os.listdir(full_dir_path):
            item_path = os.path.join(full_dir_path, item)
            rel_path = os.path.join(directory, item).replace("\\", "/")
            
            if os.path.isfile(item_path):
                # Get file info
                _, ext = os.path.splitext(item.lower())
                size = os.path.getsize(item_path)
                mtime = os.path.getmtime(item_path)
                
                artifacts.append({
                    "name": item,
                    "path": rel_path,
                    "type": "file",
                    "preview_type": self.PREVIEW_TYPES.get(ext, "unknown"),
                    "size": size,
                    "size_formatted": self._format_size(size),
                    "modified": mtime
                })
            elif os.path.isdir(item_path) and not item.startswith("."):
                # Add directory
                artifacts.append({
                    "name": item,
                    "path": rel_path,
                    "type": "directory"
                })
        
        # Sort: directories first, then files by name
        return sorted(artifacts, key=lambda x: (x["type"] != "directory", x["name"].lower()))
