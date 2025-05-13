import re
from markdown_it import MarkdownIt
from typing import List

def extract_tables(md_content: str) -> List[str]:
    """Extract HTML tables from markdown content"""
    md = MarkdownIt()
    html = md.render(md_content)
    return re.findall(r"<table.*?>.*?</table>", html, re.DOTALL)

def markdown_to_html(md_content: str) -> str:
    """Convert full markdown to HTML"""
    return MarkdownIt().render(md_content)
