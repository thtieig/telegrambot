# core/auth.py
"""Authentication management"""
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self, authorised_ids: list, authorised_usernames: list):
        self.authorised_ids = authorised_ids
        self.authorised_usernames = authorised_usernames
    
    def is_authorised(self, user_id: int, username: str, is_bot: bool) -> bool:
        """Check if user is authorised to use the bot"""
        if is_bot:
            logger.warning(f"Bot user attempted access: {user_id}")
            return False
        
        if user_id not in self.authorised_ids:
            logger.warning(f"Unauthorised user ID: {user_id}")
            return False
            
        if username not in self.authorised_usernames:
            logger.warning(f"Unauthorised username: {username}")
            return False
            
        return True
