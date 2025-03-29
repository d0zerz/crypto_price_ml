import unittest
from datetime import datetime

import pandas as pd
from pandas.testing import assert_series_equal
from prices.price_data import PriceData

# Get module logger
logger = logging.getLogger(__name__)

import logging


class TestPriceData(unittest.TestCase):
    def setUp(self):
        """Set up a sample DataFrame for testing."""
        data = [
            [datetime(2024, 12, 25, 10, 0), 100],
            [datetime(2024, 12, 26, 12, 0), 150],
            [datetime(2024, 12, 27, 14, 0), 200],
            [datetime(2024, 12, 28, 0, 0), 300],
            [datetime(2024, 12, 29, 0, 0), 400],
        ]
        self.pricesDf = pd.DataFrame(data, columns=["timestamp", "price_vs_btc"])
        self.pricesDf.set_index("timestamp", inplace=True)
        self.priceData = PriceData("fake", self.pricesDf)

    def test_find_closest_exact_match(self):
        target = datetime(2024, 12, 26, 12, 0)
        price = self.priceData.getClosestPrice(target)
        assert price == 150.0

    def test_find_closest_near_match(self):
        """Test the method with a target datetime that has no exact match."""
        target = datetime(2024, 12, 26, 9, 0)
        price = self.priceData.getClosestPrice(target)
        assert price == 150.0

    def test_find_closest_near_match_after(self):
        """Test the method with a target datetime that has no exact match."""
        target = datetime(2024, 12, 26, 13, 0)
        price = self.priceData.getClosestPrice(target)
        assert price == 150.0

    def test_find_closest_earlier_datetime(self):
        """Test the method with a target datetime earlier than all entries."""
        target = datetime(2024, 12, 24, 9, 0)
        price = self.priceData.getClosestPrice(target)
        assert price == 100.0

    def test_find_closest_halfway(self):
        """Test the method with a target datetime earlier than all entries."""
        target = datetime(2024, 12, 28, 11, 59)
        price = self.priceData.getClosestPrice(target)
        assert price == 300.0

    def test_find_closest_later_datetime(self):
        """Test the method with a target datetime later than all entries."""
        target = datetime(2025, 12, 28, 9, 0)
        price = self.priceData.getClosestPrice(target)
        assert price == 400.0


if __name__ == "__main__":
    unittest.main()
