# commands/system_commands.py
"""Basic system commands"""
from core.command_loader import BaseCommandHandler
from core.shell_utils import ShellExecutor

class SystemCommandHandler(BaseCommandHandler):
    def __init__(self):
        self.commands = {
            'uptime': ['uptime'],
            'df': ['df', '-h'],
            'last': ['last'],
        }
    
    async def can_handle(self, command: str) -> bool:
        return command in self.commands
    
    async def execute(self, message, command: str):
        if command in self.commands:
            result = ShellExecutor.execute_command(self.commands[command])
            await message.reply_text(result)
    
    async def get_help(self) -> str:
        return "System: " + ", ".join(self.commands.keys())