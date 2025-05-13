import re
from typing import List

try:
    from markdown_it import MarkdownIt
    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False

def extract_tables(md_content: str) -> List[str]:
    """Extract HTML tables from markdown content"""
    if not MARKDOWN_IT_AVAILABLE:
        return []

    md = MarkdownIt()
    html = md.render(md_content)
    return re.findall(r"<table.*?>.*?</table>", html, re.DOTALL)

def markdown_to_html(md_content: str) -> str:
    """Convert full markdown to HTML"""
    if not MARKDOWN_IT_AVAILABLE:
        return md_content

    return MarkdownIt().render(md_content)
