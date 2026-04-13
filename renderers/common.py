from __future__ import annotations


def markdown_escape(text: str) -> str:
    """Escape characters that break markdown tables and links."""
    return text.replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def html_escape(text: str) -> str:
    """Escape text for inline HTML rendering."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
