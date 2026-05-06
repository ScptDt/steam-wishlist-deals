from __future__ import annotations

from .share_html_renderer import generate_share_html as _generate_share_html


def generate_share_html(*args, **kwargs) -> str:
    """Fallback Share HTML renderer kept outside the generator boundary."""
    return _generate_share_html(*args, **kwargs)
