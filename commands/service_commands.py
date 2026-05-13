# commands/service_commands.py
"""Service management commands"""
from core.command_loader import BaseCommandHandler
from core.shell_utils import ShellExecutor

class ServiceCommandHandler(BaseCommandHandler):
    def __init__(self):
        self.commands = {
            'vpn-restart': ['sudo', 'systemctl', 'restart', 'openvpn.service'],
            'tunnel-ssh': ['sudo', 'systemctl', 'restart', 'ssh-tunnel'],
        }
    
    async def can_handle(self, command: str) -> bool:
        return command in self.commands
    
    async def execute(self, message, command: str):
        if command in self.commands:
            result = ShellExecutor.execute_command(self.commands[command])
            if result.strip():
                await message.reply_text(result)
            else:
                await message.reply_text(f"✅ {command} completed")
    
    async def get_help(self) -> str:
        return "Services: " + ", ".join(self.commands.keys())