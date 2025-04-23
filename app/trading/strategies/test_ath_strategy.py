import unittest
from trading.strategies.ath_strategy import ATHSellStrategy

class TestATHSellStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = ATHSellStrategy()

    def test_should_sell_with_sample_data(self):
        # Test data: prices in inverted format (we want them to go down)
        test_prices = [
            1962.45, 1949.24, 1897.65, 1896.93, 1855.36,
            1784.21, 1774.91, 1688.42, 1633.41, 2048.16
        ]
        
        # Test 1: Check if it detects the 25% drop from ATH
        # ATH is 1633.41, current is 2048.16
        # Drop = ((2048.16 - 1633.41) / 1633.41) * 100 = 25.4%
        self.assertTrue(self.strategy.should_sell(test_prices),
                       "Should sell due to >25% drop from ATH")

        self.assertFalse(self.strategy.should_sell(test_prices[:-1]),
                       "Should not sell with less than 25% drop from ATH")        
        
        # Test 2: Check with partial data to test plateau detection
        partial_prices = test_prices[:5]  # First 5 prices
        self.assertFalse(self.strategy.should_sell(partial_prices),
                        "Should not sell with only 5 samples")
        
        # Test 3: Check with increasing prices
        increasing_prices = [2000, 1900, 1800, 1700, 1600, 1500, 1400, 1300, 1200, 1100,1000, 900]
        self.assertFalse(self.strategy.should_sell(increasing_prices),
                       "Should sell due to >100% overall increase")
        
        # Test 4: Check with stable prices
        stable_prices = [1000, 1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009]
        self.assertFalse(self.strategy.should_sell(stable_prices),
                        "Should not sell with stable prices")
        
        # Test 5: Check with plateau after increase
        plateau_prices = [2000, 1900, 1901, 1903, 1901, 
                          1800, 1700, 1600, 1500, 1501, 
                          1502, 1503, 1504, 1502, 1503, 
                          1504
                          ]
        self.assertTrue(self.strategy.should_sell(plateau_prices),
                       "Should sell due to plateau after increase")
        
        # Test 6: Check with plateau / loss after increase
        plateau_prices = [2000, 1900, 1901, 1903, 1901, 
                          1800, 1700, 1600, 1500, 1501, 
                          1502, 1503, 1504, 1502, 1503, 
                          1554
                          ]
        self.assertTrue(self.strategy.should_sell(plateau_prices),
                       "Should sell due to plateau after increase")
        
    def test_edge_cases(self):
        # Test with empty list
        self.assertFalse(self.strategy.should_sell([]),
                        "Should not sell with empty price list")
        
        # Test with single price
        self.assertFalse(self.strategy.should_sell([1000]),
                        "Should not sell with single price")
        
        self.assertTrue(self.strategy.should_sell([1000, 1260]),
                       "Should sell with 25% increase from ATH")
        
        self.assertTrue(self.strategy.should_sell([1000, 1011]),
                       "Should sell with 1% increase from ATH")
        
        self.assertFalse(self.strategy.should_sell([1000, 1009]),
                       "Should sell with less than 1% increase from ATH")
        
        self.assertTrue(self.strategy.should_sell([1000, 1019]),
                "Should sell with 2% increase from ATH")
        
        self.assertFalse(self.strategy.should_sell([1000, 500]),
                       "Should not sell with 100% increase from ATH")

if __name__ == '__main__':
    unittest.main() 