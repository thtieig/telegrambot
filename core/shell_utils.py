# core/shell_utils.py
"""Shell command execution utilities"""
import subprocess
import logging

logger = logging.getLogger(__name__)

class ShellExecutor:
    @staticmethod
    def execute_command(command_list: list) -> str:
        """Execute a shell command safely"""
        try:
            result = subprocess.check_output(
                command_list,
                stderr=subprocess.STDOUT,
                timeout=30  # Add timeout for safety
            ).decode('utf-8', errors='replace')
        except subprocess.CalledProcessError as e:
            result = e.output.decode('utf-8', errors='replace')
        except subprocess.TimeoutExpired:
            result = "Command timed out after 30 seconds"
        except Exception as e:
            result = f'Error executing command: {str(e)}'
        
        return result