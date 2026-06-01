import os
import string
import core.exec as execmod
from core.exec import generate_password, ExecFeature
from tests.conftest import FakeMessage


def test_generate_password_length_and_charset():
    pw = generate_password(20)
    assert len(pw) == 20
    assert all(c in (string.ascii_letters + string.digits) for c in pw)


def _feature(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAMBOT_STATE_DIR", str(tmp_path))
    feat = ExecFeature()
    # never send real email
    monkeypatch.setattr(feat, "_send_email", lambda *a, **k: None)
    return feat


def test_handles_prefixes():
    feat = ExecFeature.__new__(ExecFeature)  # no __init__/mkdir
    assert feat.handles("exec ls")
    assert feat.handles("PASSWORD: abc")
    assert not feat.handles("execute foo")
    assert not feat.handles("uptime")


async def test_request_stores_state(tmp_path, monkeypatch):
    feat = _feature(tmp_path, monkeypatch)
    msg = FakeMessage()
    await feat.handle(msg, "exec echo hi")
    assert feat.password_file.exists()
    assert feat.command_file.read_text().strip() == "echo hi"
    assert "password has been sent" in msg.replies[0].lower()


async def test_wrong_password_decrements_attempts(tmp_path, monkeypatch):
    feat = _feature(tmp_path, monkeypatch)
    await feat.handle(FakeMessage(), "exec echo hi")
    msg = FakeMessage()
    await feat.handle(msg, "PASSWORD: wrong")
    assert "2 left" in msg.replies[0] or "2 " in msg.replies[0]
    assert feat.attempt_file.read_text().strip() == "1"


async def test_correct_password_runs_and_cleans_up(tmp_path, monkeypatch):
    feat = _feature(tmp_path, monkeypatch)
    captured = {}
    monkeypatch.setattr(execmod, "run_command", lambda argv: captured.update({"argv": argv}) or "OK")
    await feat.handle(FakeMessage(), "exec echo hi")
    pw = feat.password_file.read_text().strip()
    msg = FakeMessage()
    await feat.handle(msg, f"PASSWORD: {pw}")
    assert captured["argv"] == ["sudo", "bash", "-c", "echo hi"]
    assert "OK" in msg.replies[0]
    assert not feat.password_file.exists()  # cleaned up


async def test_password_without_request_is_rejected(tmp_path, monkeypatch):
    feat = _feature(tmp_path, monkeypatch)
    msg = FakeMessage()
    await feat.handle(msg, "PASSWORD: anything")
    assert "expired or invalid" in msg.replies[0].lower()
