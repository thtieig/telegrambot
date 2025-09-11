# commands/windows_commands.py
"""Windows machine management commands"""
from core.command_loader import BaseCommandHandler
from core.shell_utils import ShellExecutor

class WindowsCommandHandler(BaseCommandHandler):
    def __init__(self):
        self.commands = {
            'shutdown-nuky': ['/usr/local/bin/shutdown-nuky'],
            # You can easily add more Windows commands here later
            # 'restart-nuky': ['/usr/local/bin/restart-nuky'],
            # 'wake-nuky': ['/usr/local/bin/wake-nuky'],
        }
    
    async def can_handle(self, command: str) -> bool:
        return command in self.commands
    
    async def execute(self, message, command: str):
        if command in self.commands:
            # Add a confirmation message for destructive actions
            if 'shutdown' in command:
                await message.reply_text(f"🔄 Initiating {command}...")
            
            result = ShellExecutor.execute_command(self.commands[command])
            
            # Provide more informative feedback
            if result.strip():
                await message.reply_text(f"Result: {result}")
            else:
                await message.reply_text(f"✅ {command} completed successfully")
    
    async def get_help(self) -> str:
        return "Windows: " + ", ".join(self.commands.keys())