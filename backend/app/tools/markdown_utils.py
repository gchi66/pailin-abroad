import re
from typing import List

try:
    from markdown_it import MarkdownIt
    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False

def extract_tables(md_content: str) -> List[str]:
    """Extract HTML tables directly from markdown content (not rendered HTML)"""
    return re.findall(r"<table.*?>.*?</table>", md_content, re.DOTALL | re.IGNORECASE)

def markdown_to_html(md_content: str) -> str:
    """Convert full markdown to HTML"""
    if not MARKDOWN_IT_AVAILABLE:
        return md_content

    return MarkdownIt().render(md_content)
