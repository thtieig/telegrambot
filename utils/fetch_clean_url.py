#!/usr/bin/env python3
"""
fetch_clean_url.py

Fetch a URL and output cleaned plain text to stdout. Designed for use by the Telegram Assistant bot,
but can be run standalone.

Usage:
    fetch_clean_url.py <url>
    fetch_clean_url.py <url> [--max-chars N] [--timeout SEC] [--full]

Defaults:
    --max-chars 100000       Hard cap on output length. Prevents runaway pages.
    --timeout  20            Network timeout in seconds.
    --full                   Skip "article" extraction and clean the whole page.

Exit codes:
    0  success
    1  usage error
    2  network error
    3  parse error
    4  unsupported media type
"""

import sys
import argparse
import re
import html as html_unescape
from typing import Optional

# Force UTF-8 output regardless of the calling environment locale.
# This prevents UnicodeEncodeError on systems with latin-1 stdout.
try:
    sys.stdout.reconfigure(encoding='utf-8')  # Python 3.7+
except Exception:
    # Fallback: write via helper when printing
    pass

# Required dependency
try:
    import requests
except ImportError:
    print("ERROR: requests module not installed", file=sys.stderr)
    sys.exit(1)

# Optional dependencies
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from readability import Document as ReadabilityDocument
except Exception:
    ReadabilityDocument = None


# ------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------

def debug(msg: str) -> None:
    """Write debug lines to stderr. Silent by default unless you uncomment."""
    # print(f"[DEBUG] {msg}", file=sys.stderr)  # uncomment for troubleshooting
    pass


def normalise_newlines(text: str) -> str:
    """Strip CRs, trim lines, collapse blank runs."""
    text = re.sub(r'\r\n?', '\n', text)
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(lines)
    # Collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def is_probably_binary(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    ctype = content_type.split(';', 1)[0].strip().lower()
    # quick filter for non-text
    if ctype.startswith("text/"):
        return False
    if ctype in ("application/xhtml+xml", "application/xml", "application/json"):
        return False
    # common binary types
    if any(ctype.startswith(x) for x in (
        "image/", "audio/", "video/", "application/pdf", "application/zip", "application/gzip",
        "application/octet-stream"
    )):
        return True
    return False


def clean_with_bs4(html_text: str) -> str:
    """Strip script/style/nav cruft and return readable text."""
    if not BeautifulSoup:
        # bs4 missing: fall back to tag-strip regex
        return regex_strip_tags(html_text)

    parser = 'html.parser'
    try:
        import lxml  # noqa: F401
        parser = 'lxml'
    except Exception:
        pass

    soup = BeautifulSoup(html_text, parser)

    # remove common non-content elements
    for tag in soup(['script', 'style', 'noscript', 'iframe', 'header', 'footer', 'nav', 'form', 'aside']):
        tag.decompose()

    text = soup.get_text(separator='\n')
    text = html_unescape.unescape(text)
    return normalise_newlines(text)


def regex_strip_tags(html_text: str) -> str:
    """Very rough fallback if bs4 not installed."""
    no_script = re.sub(r'(?is)<(script|style|noscript|iframe).*?>.*?</\1>', ' ', html_text)
    # remove the rest of the tags
    txt = re.sub(r'(?s)<.*?>', ' ', no_script)
    txt = html_unescape.unescape(txt)
    return normalise_newlines(txt)


def extract_main_content(html_text: str, prefer_article: bool = True) -> str:
    """
    Try to extract just the article body if readability is available and requested.
    Fall back to whole page clean.
    """
    if prefer_article and ReadabilityDocument:
        try:
            doc = ReadabilityDocument(html_text)
            article_html = doc.summary() or ""
            if article_html.strip():
                debug("Using readability extracted article")
                return clean_with_bs4(article_html)
        except Exception as e:
            debug(f"Readability failed: {e}")

    # fallback to full-page clean
    debug("Falling back to full page clean")
    return clean_with_bs4(html_text)


def fetch(url: str, timeout: int = 20) -> requests.Response:
    """
    Fetch URL returning the Response. Caller handles decoding and content-type.
    allow_redirects defaults to True.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TelegramAssistantFetcher/1.0; +https://example.invalid)"
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    return resp


def decode_body(resp: requests.Response, max_bytes: int = 5_000_000) -> str:
    """
    Best effort decode of response body to text.
    Caps at max_bytes to avoid memory surprises.
    """
    content = resp.content[:max_bytes]
    if len(resp.content) > max_bytes:
        debug(f"Body truncated at {max_bytes} bytes")

    # Use supplied encoding if present, else detected apparent_encoding, else utf-8
    enc = resp.encoding or resp.apparent_encoding or 'utf-8'
    try:
        return content.decode(enc, errors='replace')
    except Exception:
        try:
            return content.decode('utf-8', errors='replace')
        except Exception:
            return content.decode('latin-1', errors='replace')


def write_stdout(text: str) -> None:
    """Write UTF-8 text to stdout safely."""
    data = text.encode('utf-8', errors='replace')
    try:
        sys.stdout.buffer.write(data)
        if not data.endswith(b'\n'):
            sys.stdout.buffer.write(b'\n')
    except Exception:
        # last ditch
        print(text)


# ------------------------------------------------------------------
# Main CLI
# ------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch URL and print cleaned text.")
    p.add_argument("url", help="HTTP or HTTPS URL to fetch")
    p.add_argument("--max-chars", type=int, default=100000, help="Limit output length")
    p.add_argument("--timeout", type=int, default=20, help="Network timeout seconds")
    p.add_argument("--full", action="store_true", help="Clean full page instead of article extract")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not re.match(r'^https?://', args.url, re.IGNORECASE):
        print("ERROR: Only http and https URLs are allowed", file=sys.stderr)
        sys.exit(1)

    # Fetch
    try:
        resp = fetch(args.url, timeout=args.timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"ERROR: Failed to fetch URL: {e}", file=sys.stderr)
        sys.exit(2)

    ctype = resp.headers.get('Content-Type', '')
    if is_probably_binary(ctype):
        print(f"ERROR: Unsupported content-type for text extraction: {ctype}", file=sys.stderr)
        sys.exit(4)

    # Decode
    html_text = decode_body(resp)

    # Extract
    try:
        cleaned = extract_main_content(html_text, prefer_article=not args.full)
    except Exception as e:
        print(f"ERROR: Failed to parse HTML: {e}", file=sys.stderr)
        sys.exit(3)

    # Cap output
    if len(cleaned) > args.max_chars:
        cleaned = cleaned[:args.max_chars].rstrip() + "\n\n[Output truncated]"

    write_stdout(cleaned)


if __name__ == "__main__":
    main()

