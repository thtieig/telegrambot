from core.runner import run_command


def test_run_command_returns_stdout():
    assert run_command(["echo", "hello"]).strip() == "hello"


def test_run_command_captures_stderr_on_failure():
    out = run_command(["ls", "/no/such/path/xyz"])
    assert "No such file" in out or "cannot access" in out


def test_run_command_timeout():
    out = run_command(["sleep", "5"], timeout=1)
    assert "timed out" in out.lower()
