"""Renderer package scaffold for incremental extraction.

The first refactor cut keeps public generate_* entrypoints in
steam_deals_generator.py for compatibility with current CLI, web, and desktop
flows. Focused renderer modules will be extracted here incrementally.
"""

from .common import html_escape, markdown_escape

__all__ = ["html_escape", "markdown_escape"]
