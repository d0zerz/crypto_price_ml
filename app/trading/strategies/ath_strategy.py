from typing import List
from .base_strategy import BaseSellStrategy
import logging

logger = logging.getLogger(__name__)

class ATHSellStrategy(BaseSellStrategy):
    """Selling strategy based on all-time high (ATH) price."""
    
    def should_sell(self, samples: List[float]) -> bool:
        if not samples or len(samples) < 2:
            return False
            
        # Get the all-time high (lowest number since it's inverted)
        ath = min(samples)
        current_price = samples[-1]
        initial_price = samples[0]
        
        # Calculate percentage drop from ATH
        drop_from_ath = ((current_price - ath) / ath) * 100
        drop_from_initial = ((current_price - initial_price) / initial_price) * 100

        if drop_from_initial > 1:
            logger.info(f"Selling due to 1% drop from initial: {drop_from_ath:.2f}%")
            return True

        if drop_from_ath > 10:
            logger.info(f"Selling due to 10% drop from ATH: {drop_from_ath:.2f}%")
            return True

        # Strategy 2: Check for plateau after large increase
        plateau_sample = 8
        if len(samples) >= 15:  # Need enough samples to detect plateau
            recent_samples = samples[(-1 * plateau_sample):]
            increase_over_plateau = ((recent_samples[-1] - recent_samples[0]) / recent_samples[0]) * -100
            # If range is small compared to average (less than 2%), it's a plateau
            if increase_over_plateau < 2:
                increase = drop_from_initial * -1
                if increase > 20: 
                    logger.info(f"Selling due to plateau after {increase:.2f}% increase")
                    return True
                        
        return False 