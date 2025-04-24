import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
from pandas.api.types import is_datetime64_any_dtype as is_datetime
from datetime import datetime
import time
import pandas as pd
import json
import numpy as np
from typing import Union
import re
import glob
from pathlib import Path
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 1000)

d_match = re.compile(r"\:")
year_match = re.compile(r"[0-9]{4}")
unc_quote_match = re.compile(r"[’]")
unc_dquote_match = re.compile(r"[“”]")
unc_quest_match = re.compile(r"[？]")
unc_excl_match = re.compile(r"[！]")
unc_ell_match = re.compile(r"[…]")
unc_dash_match = re.compile(r"[–‐—]")

with open("header_settings.json", "r") as file:
    header_cols = json.load(file)

def replace_unicode_specials(s: str) -> str:
    return unc_dash_match.sub('-',
           unc_ell_match.sub('...',
           unc_excl_match.sub('!',
           unc_quest_match.sub('?',
           unc_dquote_match.sub('"',
           unc_quote_match.sub("'", s)
           ))))) if s not in {pd.NA, np.nan, None} else s

def time_convert_s(time_series: pd.Series) -> pd.Series:
    # is it already a datetime?
    if is_datetime(time_series):
        return time_series
    elif time_series.dtype == "O":
        # some datetime string
        time_series_dt = pd.to_datetime(time_series)
    elif time_series.dtype == "int64":
        # Unix timestamp
        # check for milliseconds / seconds bodge
        time_series_dt = time_series.apply(lambda ts: pd.Timestamp(ts))
        if not all(time_series_dt.dt.year >= 2000):
            # Unix timestamp was in milliseconds (probably?)
            time_series_dt = time_series.apply(lambda ts: pd.Timestamp(ts, unit="ms"))
    else:
        return time_series
    return time_series_dt

def standardize_clean(df: pd.DataFrame, header_cols: dict) -> pd.DataFrame:
    quoted_fields = ["artist", "title", "album", "album_artist", "genre"]

    # rename columns
    df = df.rename(columns={df.columns[v]: k for k,v in header_cols.items()})

    # # double quote quoted fields
    # for col in [qf for qf in quoted_fields if qf in df.columns]:
    #     df.loc[:, col] = df.loc[:, col].astype(str).apply(lambda s: f'"{s}"')

    # unicode specials
    df["artist"] = df["artist"].apply(replace_unicode_specials)
    df["title"] = df["title"].apply(replace_unicode_specials)
    df["album"] = df["album"].apply(replace_unicode_specials)
    df["album_artist"] = df["album_artist"].apply(replace_unicode_specials)

    # event times
    df["time_local"] = time_convert_s(df["time_local"])
    df["time_gmt"] = time_convert_s(df["time_gmt"])

    # duration times
    # convert to milliseconds int
    if df["duration"].dtype == "O":
        df["duration"] = df["duration"].apply(lambda t: datetime.strptime(t, "%M:%S.%f")
                                              if len(d_match.findall(t)) == 1
                                              else datetime.strptime(t, "%H:%M:%S.%f")) \
                                       .apply(lambda dt: int(dt.hour * 60 * 60 * 1e3)
                                                         + int(dt.minute * 60 * 1e3)
                                                         + int(dt.second * 1e3)
                                                         + int(dt.microsecond / 1e3))
    else:
        # if it's actually in seconds and not milliseconds
        # certain songs (short songs) durations may not be picked up?
        # fill NA with 0 and fix later...
        df["duration"] = df["duration"].fillna(0).astype(int)
        if any((df["duration"] < 1000) & (df["duration"] > 0)):
            df["duration"] = df["duration"] * 1000

    # year
    # sometimes a date...
    try:
        df["release_year"] = df["release_year"].apply(lambda y: int(year_match.findall(y)[0]))
    except KeyError as e:
        pass
        # print(e)

    return df

def load_data():
    start_time = time.time()
    # header_cols based on filenames
    for idx, db in enumerate(glob.glob("data/*.csv")):
        file_path = Path(db)
        file_name = file_path.stem
        if idx == 0:
            df = standardize_clean(pd.read_csv(file_path), header_cols=header_cols[file_name])
        else:
            df = pd.concat((df, standardize_clean(pd.read_csv(file_path), header_cols=header_cols[file_name])))
    end_time = time.time()
    print(f"Data loaded in {round(end_time - start_time, 2)} s")
    return df.sort_values("time_local")

def write_data(df: pd.DataFrame):
    combined_path = Path("data/combined")
    if not combined_path.is_dir():
        combined_path.mkdir()
    df.to_csv(combined_path / "combined.csv", index=False)
    print(f"Combined dataframe written to {combined_path}/combined.csv\n")

if __name__ == "__main__":
    df = load_data()
    write_data(df)
    #df = pd.read_csv("data/foobar2000.csv")
    # dff = pd.read_csv("data/pano_scrobbler.csv")
    #new_df = standardize_clean(df, header_cols["foobar2000"])