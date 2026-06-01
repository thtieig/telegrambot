import pytest
from core.output import looks_like_url, sanitise, chunk, send_output
from tests.conftest import FakeMessage


def test_looks_like_url():
    assert looks_like_url("https://example.com")
    assert looks_like_url("  http://x.y")
    assert not looks_like_url("hello world")
    assert not looks_like_url("ftp://x")


def test_sanitise_strips_control_chars_but_keeps_newline_tab():
    assert sanitise("a\x00b\tc\nd") == "ab\tc\nd"


def test_chunk_splits_long_text():
    text = "\n".join(f"line{i}" for i in range(2000))
    parts = chunk(text, max_len=100)
    assert len(parts) > 1
    assert all(len(p) <= 100 for p in parts)


def test_chunk_empty_returns_placeholder():
    assert chunk("") == ["[no text returned]"]


async def test_send_output_replies_in_chunks():
    msg = FakeMessage()
    await send_output(msg, "hello", max_len=100)
    assert msg.replies == ["hello"]
