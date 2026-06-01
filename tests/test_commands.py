import os
import stat
from core.commands import read_description, discover, resolve, Command


def _write_script(path, body, executable=True):
    with open(path, "w") as f:
        f.write(body)
    if executable:
        os.chmod(path, 0o755)


def test_read_description_parses_second_line(tmp_path):
    p = tmp_path / "foo"
    _write_script(p, "#!/bin/bash\n# description: Does a thing\necho hi\n")
    assert read_description(str(p)) == "Does a thing"


def test_read_description_missing_returns_empty(tmp_path):
    p = tmp_path / "foo"
    _write_script(p, "#!/bin/bash\necho hi\n")
    assert read_description(str(p)) == ""


def test_discover_finds_executables_only(tmp_path):
    _write_script(tmp_path / "run_me", "#!/bin/bash\necho a\n")
    _write_script(tmp_path / "not_exec", "#!/bin/bash\necho b\n", executable=False)
    cmds = discover([str(tmp_path)])
    assert "run_me" in cmds
    assert "not_exec" not in cmds


def test_discover_scripts_override_builtin(tmp_path):
    builtin = tmp_path / "builtin"
    scripts = tmp_path / "scripts"
    builtin.mkdir()
    scripts.mkdir()
    _write_script(builtin / "df", "#!/bin/bash\necho builtin\n")
    _write_script(scripts / "df", "#!/bin/bash\necho override\n")
    cmds = discover([str(builtin), str(scripts)])
    assert cmds["df"].path == str(scripts / "df")


def test_resolve_splits_name_and_args(tmp_path):
    _write_script(tmp_path / "restart", "#!/bin/bash\necho x\n")
    cmds = discover([str(tmp_path)])
    cmd, args = resolve("restart router now", cmds)
    assert isinstance(cmd, Command)
    assert cmd.name == "restart"
    assert args == ["router", "now"]


def test_resolve_unknown_returns_none(tmp_path):
    cmds = discover([str(tmp_path)])
    assert resolve("nope", cmds) is None
