import logging
import sys
import types


def test_httpx_request_lines_stay_out_of_the_log(monkeypatch):
    """httpx logs every request URL at INFO, and Telegram URLs carry the bot token."""
    # config.py is deployed by Ansible and holds the real token; never in the repo.
    config = types.ModuleType("config")
    config.bot_token, config.id_a, config.username, config.log_level = "test", 1, "test", "INFO"
    monkeypatch.setitem(sys.modules, "config", config)

    import telegrambot  # noqa: F401  (configures logging at import time)

    # The logger's own level, not the effective one: pytest's log capture changes the root.
    assert logging.getLogger("httpx").level >= logging.WARNING
