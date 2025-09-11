# core/command_loader.py
"""Dynamic command loading system"""
import os
import importlib.util
import logging
from typing import Dict
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class BaseCommandHandler(ABC):
    """Base class for all command handlers"""
    
    @abstractmethod
    async def can_handle(self, command: str) -> bool:
        """Check if this handler can process the given command"""
        pass
    
    @abstractmethod
    async def execute(self, message, command: str):
        """Execute the command"""
        pass
    
    @abstractmethod
    async def get_help(self) -> str:
        """Return help text for this handler's commands"""
        pass

class CommandLoader:
    def __init__(self, commands_dir: str = "commands"):
        self.commands_dir = commands_dir
        self.handlers = {}
    
    async def load_all_commands(self) -> Dict[str, BaseCommandHandler]:
        """Load all command handlers from the commands directory"""
        if not os.path.exists(self.commands_dir):
            logger.warning(f"Commands directory {self.commands_dir} not found")
            return {}
        
        handlers = {}
        
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                module_name = filename[:-3]  # Remove .py extension
                
                try:
                    handler = await self._load_handler(module_name)
                    if handler:
                        handlers[module_name] = handler
                        logger.info(f"Loaded command handler: {module_name}")
                except Exception as e:
                    logger.error(f"Failed to load handler {module_name}: {e}")
        
        return handlers
    
    async def _load_handler(self, module_name: str) -> BaseCommandHandler:
        """Load a specific command handler"""
        module_path = os.path.join(self.commands_dir, f"{module_name}.py")
        
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Look for a handler class that inherits from BaseCommandHandler
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, BaseCommandHandler) and 
                attr != BaseCommandHandler):
                return attr()
        
        logger.warning(f"No valid handler found in {module_name}")
        return None
