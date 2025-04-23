import unittest
from trading.strategies.quick_drop_strategy import QuickDropSellStrategy

class TestQuickDropSellStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = QuickDropSellStrategy()

    def test_empty_samples(self):
        """Test that empty or single sample returns False"""
        self.assertFalse(self.strategy.should_sell([]))
        self.assertFalse(self.strategy.should_sell([100.0]))

    def test_no_drop(self):
        """Test that no price drop returns False"""
        samples = [100.0, 100.0, 100.0]
        self.assertFalse(self.strategy.should_sell(samples))

    def test_small_drop(self):
        """Test that small drop (<1%) returns False"""
        samples = [100.0, 100.5]  # 0.5% increase (inverted: 0.5% drop)
        self.assertFalse(self.strategy.should_sell(samples))

    def test_significant_drop(self):
        """Test that significant drop (>1%) returns True"""
        samples = [100.0, 101.1]  # 1.1% increase (inverted: 1.1% drop)
        self.assertTrue(self.strategy.should_sell(samples))

    def test_large_drop(self):
        """Test that large drop returns True"""
        samples = [100.0, 105.0]  # 5% increase (inverted: 5% drop)
        self.assertTrue(self.strategy.should_sell(samples))

    def test_multiple_samples(self):
        """Test with multiple samples, only checking last two"""
        samples = [100.0, 99.0, 98.0, 99.2]  # Last change: 1.2% increase (inverted: 1.2% drop)
        self.assertTrue(self.strategy.should_sell(samples))

if __name__ == '__main__':
    unittest.main() 