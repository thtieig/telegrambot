import os
from core.commands import discover, resolve
from core.runner import run_command
from core.output import send_output, looks_like_url
from tests.conftest import FakeMessage


def _script(path, body):
    with open(path, "w") as f:
        f.write(body)
    os.chmod(path, 0o755)


async def test_end_to_end_command_run(tmp_path):
    _script(tmp_path / "greet", "#!/bin/bash\n# description: greet\necho \"hi $1\"\n")
    commands = discover([str(tmp_path)])

    text = "greet world"
    assert not looks_like_url(text)
    cmd, args = resolve(text, commands)
    result = run_command([cmd.path] + args)

    msg = FakeMessage()
    await send_output(msg, result)
    assert msg.replies == ["hi world"]


async def test_url_normalisation_routes_to_url_command(tmp_path):
    _script(tmp_path / "url", "#!/bin/bash\necho \"fetched $1\"\n")
    commands = discover([str(tmp_path)])

    text = "https://example.com"
    assert looks_like_url(text)
    text = f"url {text}"
    cmd, args = resolve(text, commands)
    assert cmd.name == "url"
    assert args == ["https://example.com"]
