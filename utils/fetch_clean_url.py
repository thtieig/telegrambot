#!/usr/bin/env python3
"""
fetch_clean_url.py

Fetch a URL and output cleaned plain text to stdout.

Usage:
    fetch_clean_url.py <url> [--max-chars N]

Exit codes:
    0  success
    1  usage error
    2  network error
    3  parsing error
"""

import sys
import argparse
import re

try:
    import requests
except ImportError:
    print("ERROR: requests module not installed", file=sys.stderr)
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from readability import Document as ReadabilityDocument
except Exception:
    ReadabilityDocument = None


def normalise_newlines(text: str) -> str:
    text = re.sub(r'\r\n?', '\n', text)
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def clean_with_bs4(html_text: str) -> str:
    if not BeautifulSoup:
        return html_text  # fallback

    parser = 'html.parser'
    try:
        import lxml  # noqa: F401
        parser = 'lxml'
    except Exception:
        pass

    soup = BeautifulSoup(html_text, parser)
    for tag in soup(['script', 'style', 'noscript', 'iframe']):
        tag.decompose()
    text = soup.get_text(separator='\n')
    return normalise_newlines(text)


def extract_main_content(html_text: str) -> str:
    if ReadabilityDocument:
        try:
            doc = ReadabilityDocument(html_text)
            article_html = doc.summary()
            if article_html:
                return clean_with_bs4(article_html)
        except Exception:
            pass
    return clean_with_bs4(html_text)


def fetch(url: str, timeout: int = 15) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TelegramBotFetcher/1.0; +https://example.invalid)"
    }
    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding or 'utf-8'
    return resp.text


def main():
    parser = argparse.ArgumentParser(description="Fetch URL and print cleaned text.")
    parser.add_argument("url", help="HTTP or HTTPS URL to fetch")
    parser.add_argument("--max-chars", type=int, default=100000, help="Limit output length to avoid runaway pages")
    args = parser.parse_args()

    if not re.match(r'^https?://', args.url, re.IGNORECASE):
        print("ERROR: Only http and https URLs are allowed", file=sys.stderr)
        sys.exit(1)

    try:
        html_text = fetch(args.url)
    except Exception as e:
        print(f"ERROR: Failed to fetch URL: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        cleaned = extract_main_content(html_text)
    except Exception as e:
        print(f"ERROR: Failed to parse HTML: {e}", file=sys.stderr)
        sys.exit(3)

    if len(cleaned) > args.max_chars:
        cleaned = cleaned[:args.max_chars].rstrip() + "\n\n[Output truncated]"

    print(cleaned.encode('utf-8', errors='replace').decode('utf-8'))


if __name__ == "__main__":
    main()

