# commands/service_commands.py
"""Service management commands"""
from core.command_loader import BaseCommandHandler
from core.shell_utils import ShellExecutor

class ServiceCommandHandler(BaseCommandHandler):
    def __init__(self):
        self.commands = {
            'vpn-restart': ['sudo', 'systemctl', 'restart', 'openvpn.service'],
            'kodi stop': ['sudo', 'manage_kodi', 'off'],
            'kodi start': ['sudo', 'manage_kodi', 'on'],
            'upgrade raspbxino': ['sudo', 'upgrade_raspbxino'],
            'tunnel-ssh': ['/usr/local/bin/ssh-port-forward.sh'],
        }
    
    async def can_handle(self, command: str) -> bool:
        return command in self.commands
    
    async def execute(self, message, command: str):
        if command in self.commands:
            result = ShellExecutor.execute_command(self.commands[command])
            await message.reply_text(result)
    
    async def get_help(self) -> str:
        return "Services: " + ", ".join(self.commands.keys())