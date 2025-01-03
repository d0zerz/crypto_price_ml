from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List

import pandas as pd
import requests
import json

EVENTS_URL = "https://api.augmento.ai/v0.1/events/aggregated"

#positive
BULLISH=38
OPTIMISTIC=91
HAPPY=39
EUPHORIC_EXCITED = 23

POSITIVE_INDICIES = [BULLISH,OPTIMISTIC,HAPPY,EUPHORIC_EXCITED]

#negative
BEARISH = 26
PESSIMISTIC = 1
SAD = 53
FEARFUL=14
ANGRY = 6
MISTRUSTFUL = 73
PANICKING = 54
ANNOYED = 85

NEGATIVE_INDICIES = [BEARISH, PESSIMISTIC, SAD, FEARFUL, ANGRY, MISTRUSTFUL, PANICKING, ANNOYED]

PICKLE_FILE_LOCATION="sentiment/augmento_price_history.pickle"

class AugmentoClient:
    def __init__(self, headers = None, auth=None) -> None:
        self.headers = headers if headers else {}
        self.auth = auth

    def get_sentiment_for_dates(self, start: datetime, end: datetime) -> pd.DataFrame:
        
        url = EVENTS_URL

        params = {
        "source" : "twitter",
        "coin" : "bitcoin",
        "bin_size" : "24H",
        "count_ptr" : 1000,
        "start_ptr" : 0,
        "start_datetime" : start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_datetime" : end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        r = requests.request("GET", url, params=params)
        content = r.content
        return self._convert_augmento_response(json.loads(content))
    
    def _convert_augmento_response(self, response_dict) -> pd.DataFrame:
        sentiments = []

        for record in response_dict:
            counts = record["counts"]
            positive = sum(counts[i] for i in POSITIVE_INDICIES)
            negative = sum(counts[i] for i in NEGATIVE_INDICIES)
            date_obj = datetime.strptime(record["datetime"], "%Y-%m-%dT%H:%M:%SZ")
            sentiments.append([date_obj, positive, negative])
            
        columns = ['date', 'positive', 'negative']
        df = pd.DataFrame(sentiments, columns=columns)
        if sentiments:
            df["date"] = pd.to_datetime(df["date"], utc=True)
            df.set_index('date', inplace=True)
        return df
    
    def dumpSentimentsToFile(self, filename: str):
        df = self.get_all_sentiments()
        df.to_pickle(filename)
    
    def get_all_sentiments(self, fromStorage=False):
        if fromStorage:
            return self._loadPickleFile(PICKLE_FILE_LOCATION)
        startdate = datetime(year=2017, month=1, day=1)
        enddate = datetime(year=2025, month=9, day=1)
        
        dataframes = []
        curdate = startdate
        while curdate < enddate:
            dataframes.append(self.get_sentiment_for_dates(curdate, curdate + relativedelta(months=6)))
            curdate = curdate + relativedelta(months=6)
        dataframe = pd.concat(dataframes, ignore_index=False)
        return dataframe

    def _loadPickleFile(self, filename) -> pd.DataFrame:
        return pd.read_pickle(filename)

#AugmentoClient().dumpSentimentsToFile(PICKLE_FILE_LOCATION)

# sentiments = AugmentoClient().get_all_sentiments(fromStorage=True)
