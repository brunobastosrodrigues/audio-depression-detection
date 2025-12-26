from abc import ABC, abstractmethod
import numpy as np
from typing import Union


class UserRepositoryPort(ABC):
    @abstractmethod
    def load_all_user_embeddings(self) -> dict:
        pass

    @abstractmethod
    def save_user_embedding(
        self, user_id: Union[int, str], embedding: np.ndarray, overwrite: bool = False
    ):
        pass

    @abstractmethod
    def delete_user_embedding(self, user_id: Union[int, str], embedding: np.ndarray):
        pass
