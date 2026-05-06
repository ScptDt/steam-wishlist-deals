from __future__ import annotations

from .html_renderer import generate_html as _generate_html


def generate_html(*args, **kwargs) -> str:
    """Fallback HTML report renderer kept outside the generator boundary."""
    return _generate_html(*args, **kwargs)
