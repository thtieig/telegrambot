# commands/url_fetch.py
import os
import sys
from core.command_loader import BaseCommandHandler
from core.shell_utils import ShellExecutor
from core.message_utils import send_chunked_text, is_url_like

class UrlFetchHandler(BaseCommandHandler):
    def __init__(self):
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.fetch_script = os.path.join(script_dir, 'utils', 'fetch_clean_url.py')
    
    async def can_handle(self, command: str) -> bool:
        lower_cmd = command.lower()
        return (lower_cmd.startswith('url ') or 
                lower_cmd.startswith('fetch ') or 
                is_url_like(command))
    
    async def execute(self, message, command: str):
        lower_cmd = command.lower()
        url = None
        if lower_cmd.startswith('url '):
            url = command.split(' ', 1)[1].strip()
        elif lower_cmd.startswith('fetch '):
            url = command.split(' ', 1)[1].strip()
        elif is_url_like(command):
            url = command.strip()
        if not url:
            await message.reply_text('No URL provided')
            return

        if not os.path.exists(self.fetch_script) or not os.access(self.fetch_script, os.X_OK):
            await message.reply_text(f'Fetch script not found or not executable at {self.fetch_script}')
            return

        await message.reply_text('Fetching URL, please wait...')

        #result = ShellExecutor.execute_command(['python3', self.fetch_script, url, '--accept-cookies', '--full'])
        result = ShellExecutor.execute_command(['python3', self.fetch_script, url])

        # Only decode once safely
        if isinstance(result, bytes):
            try:
                result = result.decode('utf-8')
            except UnicodeDecodeError:
                result = result.decode('utf-8', errors='replace')

        # Remove control characters Telegram dislikes
        import unicodedata
        result = ''.join(c for c in result if unicodedata.category(c)[0] != 'C' or c in '\n\t')

        await send_chunked_text(message, result)
    
    async def get_help(self) -> str:
        return "URL: url <http[s]://...>, fetch <http[s]://...>, or just paste a URL"
