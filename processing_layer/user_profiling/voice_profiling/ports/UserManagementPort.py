from abc import ABC, abstractmethod
from typing import Dict, List


class UserManagementPort(ABC):
    @abstractmethod
    def get_all_users(self) -> List[Dict]:
        """Get all registered users."""
        pass

    @abstractmethod
    def delete_user(self, user_id: str) -> bool:
        """Delete a user by ID."""
        pass
