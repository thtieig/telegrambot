# commands/url_fetch.py
"""URL fetching functionality"""
import os
import sys
from core.command_loader import BaseCommandHandler
from core.shell_utils import ShellExecutor
from core.message_utils import send_chunked_text, is_url_like

class UrlFetchHandler(BaseCommandHandler):
    def __init__(self):
        # Get the fetch script path relative to the main script
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.fetch_script = os.path.join(script_dir, 'utils', 'fetch_clean_url.py')
    
    async def can_handle(self, command: str) -> bool:
        lower_cmd = command.lower()
        return (lower_cmd.startswith('url ') or 
                lower_cmd.startswith('fetch ') or 
                is_url_like(command))
    
    async def execute(self, message, command: str):
        # Extract URL from command
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
        
        # Check if fetch script exists
        if not os.path.exists(self.fetch_script):
            await message.reply_text(f'Fetch script not found at {self.fetch_script}')
            return
        
        if not os.access(self.fetch_script, os.R_OK):
            await message.reply_text(f'Fetch script not readable at {self.fetch_script}')
            return
        
        # Execute fetch with explicit python interpreter
        try:
            result = ShellExecutor.execute_command([sys.executable, self.fetch_script, url])
            await send_chunked_text(message, result)
        except Exception as e:
            await message.reply_text(f'Error fetching URL: {str(e)}')
    
    async def get_help(self) -> str:
        return """URL fetching commands:
• url <http[s]://...> - Fetch and clean a webpage
• fetch <http[s]://...> - Same as url command  
• Just paste a URL - Automatically detected and fetched

The fetcher extracts the main content from web pages and returns clean text."""