import json
import logging
import os

from core import rich
from core.runner import run_command


def _out(obj, same_line=False):
    return rich.MARKER + (" " if same_line else "\n") + json.dumps(obj)


def test_plain_output_is_not_rich():
    assert rich.parse("hello\n") is None
    assert rich.parse("") is None
    assert rich.parse("x\n#telegram-json\n{}") is None  # marker must be first
    assert rich.parse('#telegram-jsonx {"text": "a"}') is None


def test_parse_full_object():
    r = rich.parse(_out({"text": "hi", "buttons": [[{"text": "A", "cmd": "a 1"}, {"text": "B", "cmd": "b"}], [{"text": "C", "cmd": "c"}]],
                         "edit": False, "silent": False}))
    assert r.text == "hi"
    assert r.buttons == [[{"text": "A", "cmd": "a 1"}, {"text": "B", "cmd": "b"}], [{"text": "C", "cmd": "c"}]]
    assert r.edit is False and r.silent is False


def test_marker_and_json_on_same_line():
    r = rich.parse(_out({"silent": True}, same_line=True))
    assert r.silent is True and r.text == ""


def test_malformed_json_falls_back_to_plain():
    assert rich.parse("#telegram-json\n{not json") is None
    assert rich.parse("#telegram-json\n[1, 2]") is None
    assert rich.parse("#telegram-json\n") is None


def test_oversize_cmd_dropped_with_warning(caplog):
    long_cmd = "x" * 65
    multibyte = "é" * 33  # 66 bytes, 33 chars
    ok = "y" * 64
    with caplog.at_level(logging.WARNING):
        r = rich.parse(_out({"text": "t", "buttons": [[{"text": "L", "cmd": long_cmd}, {"text": "M", "cmd": multibyte},
                                                         {"text": "OK", "cmd": ok}], [{"text": "L2", "cmd": long_cmd}]]}))
    assert r.buttons == [[{"text": "OK", "cmd": ok}]]  # emptied row removed
    assert "over 64 bytes" in caplog.text


def test_malformed_buttons_dropped():
    r = rich.parse(_out({"text": "t", "buttons": [[{"text": "no cmd"}, "junk", {"text": 1, "cmd": "c"}], "notarow"]}))
    assert r.buttons == []
    assert rich.parse(_out({"text": "t", "buttons": "nope"})).buttons == []


def test_edit_decision():
    default, no_edit, edit = rich.Rich(), rich.Rich(edit=False), rich.Rich(edit=True)
    assert rich.should_edit(default, "button") is True
    assert rich.should_edit(no_edit, "button") is False
    assert rich.should_edit(edit, "button") is True
    for r in (default, no_edit, edit):
        assert rich.should_edit(r, "text") is False


def test_non_bool_edit_and_silent_ignored():
    r = rich.parse(_out({"text": "t", "edit": "no", "silent": "yes"}))
    assert r.edit is None and r.silent is False


def test_keyboard():
    assert rich.keyboard(rich.Rich(text="t")) is None
    kb = rich.keyboard(rich.Rich(buttons=[[{"text": "A", "cmd": "a"}, {"text": "B", "cmd": "b"}], [{"text": "C", "cmd": "c"}]]))
    rows = kb.inline_keyboard
    assert [[b.text for b in r] for r in rows] == [["A", "B"], ["C"]]
    assert rows[0][1].callback_data == "b"


def test_script_env():
    env = rich.script_env(42, "text", message_id=7)
    assert env["TG_CHAT_ID"] == "42" and env["TG_TRIGGER"] == "text"
    assert "TG_MESSAGE_ID" not in env  # button trigger only
    env = rich.script_env(42, "button", message_id=7)
    assert env["TG_TRIGGER"] == "button" and env["TG_MESSAGE_ID"] == "7"
    assert env["PATH"] == os.environ["PATH"]


def test_runner_passes_env():
    env = rich.script_env(9, "button", 3)
    out = run_command(["sh", "-c", 'echo "$TG_CHAT_ID $TG_TRIGGER $TG_MESSAGE_ID"'], env=env)
    assert out.strip() == "9 button 3"
    assert run_command(["echo", "plain"]).strip() == "plain"  # env optional
