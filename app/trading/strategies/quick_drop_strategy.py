from typing import List
from .base_strategy import BaseSellStrategy
import logging

logger = logging.getLogger(__name__)

class QuickDropSellStrategy(BaseSellStrategy):
    """Selling strategy that triggers when price drops more than 1% from previous sample."""
    
    def should_sell(self, samples: List[float]) -> bool:
        if not samples or len(samples) < 2:
            return False
            
        current_price = samples[-1]
        previous_price = samples[-2]
        
        # Calculate percentage drop from previous sample
        # Formula: ((new - old) / old) * 100
        pct_drop = ((current_price - previous_price) / previous_price) * 100
        
        # Since we're dealing with inverted prices (lower is better),
        # we want to sell when the drop is positive (price went up)
        if pct_drop > .1:
            logger.info(f"Selling due to quick drop: {pct_drop:.2f}% from previous sample")
            return True
            
        return False 