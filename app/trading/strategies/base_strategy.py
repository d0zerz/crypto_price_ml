from abc import ABC, abstractmethod
from typing import List

class BaseSellStrategy(ABC):
    """Base class for all selling strategies."""
    
    @abstractmethod
    def should_sell(self, samples: List[float]) -> bool:
        """
        Determine if we should sell based on the given price samples.
        
        Args:
            samples: List of price samples in chronological order
            
        Returns:
            bool: True if we should sell, False otherwise
        """
        pass 