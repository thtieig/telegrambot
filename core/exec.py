"""The single built-in stateful command: email-verified arbitrary execution.

State files live under $TELEGRAMBOT_STATE_DIR (default /var/lib/telegrambot),
mode 0600. The `config` import is local to _send_email so this module imports
without a config.py present.
"""
import os
import secrets
import string
from pathlib import Path
from email.mime.text import MIMEText

from core.runner import run_command

_ALPHABET = string.ascii_letters + string.digits


def generate_password(length: int = 12) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


class ExecFeature:
    def __init__(self):
        self._state_dir = Path(os.environ.get("TELEGRAMBOT_STATE_DIR", "/var/lib/telegrambot"))
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self.password_file = self._state_dir / "exec_password.txt"
        self.attempt_file = self._state_dir / "exec_attempts.txt"
        self.command_file = self._state_dir / "exec_command.txt"
        self.max_attempts = 3

    def handles(self, command: str) -> bool:
        return command == "exec" or command.startswith("exec ") or command.startswith("PASSWORD")

    async def handle(self, message, command: str):
        if command.startswith("PASSWORD"):
            await self._verify(message, command)
        else:
            await self._request(message, command)

    async def _request(self, message, command: str):
        password = generate_password()
        self._write(self.password_file, password)
        self._write(self.attempt_file, "0")
        self._write(self.command_file, command[len("exec"):].strip())
        self._send_email("Your exec Command Password", f"PASSWORD: {password}")
        await message.reply_text(
            'A temporary password has been sent to your email. '
            'Reply with "PASSWORD: yourpassword" to execute the command.'
        )

    async def _verify(self, message, command: str):
        if not self.password_file.exists():
            await message.reply_text("Password has expired or invalid. Please generate a new exec command.")
            return
        parts = command.split(" ", 1)
        if len(parts) < 2:
            await message.reply_text('Invalid password format. Reply with "PASSWORD: yourpassword".')
            return
        if parts[1].strip() != self.password_file.read_text().strip():
            await self._failed_attempt(message)
            return
        await self._run(message)

    async def _failed_attempt(self, message):
        attempts = int(self.attempt_file.read_text().strip()) + 1
        self._write(self.attempt_file, str(attempts))
        if attempts >= self.max_attempts:
            await message.reply_text("Too many failed attempts. The password has expired.")
            self._cleanup()
        else:
            await message.reply_text(f"Unauthorised access attempt! {self.max_attempts - attempts} attempts left.")

    async def _run(self, message):
        import core.exec as _self_module
        cmd = self.command_file.read_text().strip()
        result = _self_module.run_command(["sudo", "bash", "-c", cmd])
        await message.reply_text(f"Command execution result:\n\n{result}")
        self._cleanup()

    def _write(self, path: Path, content: str):
        path.write_text(content)
        os.chmod(path, 0o600)

    def _send_email(self, subject: str, body: str):
        import smtplib
        from config import recipient_email, email_address, email_password, smtp_server, smtp_port
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = email_address
        msg["To"] = recipient_email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.sendmail(email_address, recipient_email, msg.as_string())

    def _cleanup(self):
        for f in (self.password_file, self.attempt_file, self.command_file):
            if f.exists():
                f.unlink()
