from __future__ import annotations

import html
from typing import Optional


def escape_html(value: Optional[str]) -> str:
    if value is None:
        return ""
    return html.escape(value, quote=True)

