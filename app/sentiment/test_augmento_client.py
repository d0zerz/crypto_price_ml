from datetime import datetime
import pytest
from sentiment import Sentiment
from augmento_client import AugmentoClient

TEST_DATA = [
   {
      "counts":[2,9,34,37,21,11,15,1,12,11,9,11,242,140,6,8,2,2,12,213,0,6,627,56,11,1,45,38,73,38,15,0,3,3,56,2,29,6,181,8,2,6,21,13,2,3,9,3,66,91,22,2,0,0,0,24,44,16,16,3,206,2,40,290,55,100,14,41,4,14,0,4,266,3,7,307,6,151,3,107,18,7,1,95,11,0,1346,54,1,16,1,51,289],
      "datetime":"2020-06-01T00:00:00Z",
      "t_epoch":1590969600
   },
   {
      "counts":[8,9,38,58,16,7,11,1,14,12,10,20,297,127,14,17,2,2,5,264,3,16,1172,66,21,3,85,34,120,59,18,0,8,8,66,2,22,5,211,13,1,15,42,2,1,1,19,4,44,113,14,14,4,2,2,22,51,18,14,7,264,0,29,292,35,99,14,24,7,7,0,3,294,2,10,361,3,139,12,114,21,4,2,133,11,1,1843,61,3,22,1,74,353],
      "datetime":"2020-06-02T00:00:00Z",
      "t_epoch":1591056000
   }
]

class TestAugmentoClient:
   def test_get_sentiments(self):
      client = AugmentoClient()
      sentiments = client.get_sentiment_for_dates(start=datetime(year=2020, month=6, day=1), end=datetime(year=2020, month=6, day=3))
      expected1 = Sentiment(num_positive=296, num_negative=78, date=datetime(year=2020, month=6, day=1))
      expected2 = Sentiment(num_positive=364, num_negative=126, date=datetime(year=2020, month=6, day=2))
      assert sentiments[0] == expected1
      assert sentiments[1] == expected2

   def test_convert_augmento_response(self):
      client = AugmentoClient()
      sentiments = client._convert_augmento_response(TEST_DATA)
      expected1 = Sentiment(num_positive=296, num_negative=78, date=datetime(year=2020, month=6, day=1))
      expected2 = Sentiment(num_positive=364, num_negative=126, date=datetime(year=2020, month=6, day=2))
      assert sentiments[0] == expected1
      assert sentiments[1] == expected2
