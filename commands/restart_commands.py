# commands/restart_commands.py
"""Device restart commands"""
from core.command_loader import BaseCommandHandler
from core.shell_utils import ShellExecutor

class RestartCommandHandler(BaseCommandHandler):
    def __init__(self):
        self.devices = {
            'router': ['sudo', 'restart_device', 'router'],
            'raspberrino': ['sudo', 'restart_device', 'raspberrino'],
            'raspbxino': ['sudo', 'restart_device', 'raspbxino'],
        }
    
    async def can_handle(self, command: str) -> bool:
        return command.startswith('restart ')
    
    async def execute(self, message, command: str):
        if not command.startswith('restart '):
            return
            
        device = command.split('restart', 1)[1].strip()
        
        if device in self.devices:
            result = ShellExecutor.execute_command(self.devices[device])
            await message.reply_text(result)
        else:
            await message.reply_text('Usage: restart (router|raspberrino|raspbxino)')
    
    async def get_help(self) -> str:
        devices = "|".join(self.devices.keys())
        return f"Restart: restart ({devices})"