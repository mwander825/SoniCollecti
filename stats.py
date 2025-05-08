import numpy as np
import pandas as pd
from typing import Tuple, Iterable
from pathlib import Path
import re
import datetime

def get_new_artists(df: pd.DataFrame, start_date: str=None, end_date: str=None, tz="local"):
    ts = f"time_{tz}"
    df[ts] = pd.to_datetime(df[ts])

    start_date = pd.to_datetime(start_date).date() if start_date is not None else \
        pd.to_datetime(df[ts].max().to_numpy().astype('datetime64[M]')).date()
    end_date = pd.to_datetime(end_date).date() if end_date is not None else \
        (pd.to_datetime(df[ts].max()) + pd.tseries.offsets.MonthEnd(0)).date()

    df[ts] = df[ts].dt.date

    # now = datetime.datetime.now()
    # this_month = datetime.datetime(now.year, now.month, 1)
    old_artists = set(df[df[ts] < start_date]["artist"].unique())

    new_artists = sorted(list(set(df[(df[ts] >= start_date) & (df[ts] <= end_date)]["artist"].unique()).difference(old_artists)))

    return new_artists

if __name__ == "__main__":
    df = pd.read_csv("data/combined/combined.csv")
    print(get_new_artists(df, start_date="2025-02-01", end_date="2025-02-28"))