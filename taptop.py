from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
import numpy as np
import pandas as pd
from typing import Tuple, Iterable
from pathlib import Path
import re
import json
from copy import deepcopy
import h5py
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 1000)

# Inspired by https://www.tapmusic.net/

def load_covers(df: pd.DataFrame=None, mbids: Iterable=None) -> Tuple[pd.DataFrame, dict]:
    file_path = Path("data/combined/mb_covers.h5")
    df_mbid = pd.read_csv("data/combined/mb_ids.csv")
    if df is not None:
        # assumedly filtered down a bit
        df_mbid = df_mbid.merge(df, on=['artist', 'album']).loc[:, ["artist", "album", "mbid"]]
    elif mbids is not None:
        df_mbid = df_mbid[df_mbid.isin(mbids)]

    with h5py.File(file_path, 'r') as file:
        if df is not None or mbids is not None:
            covers_dict = {k.decode(): v for k,v in zip(file["mbid"][:], file["covers"][:]) \
                           if k.decode() in set(df_mbid["mbid"].unique())}
        else:
            covers_dict = {k.decode(): v for k, v in zip(file["mbid"][:], file["covers"][:])}

    return df_mbid, covers_dict

def newline_name(s: str, max_char: int) -> str:
    if len(s) > max_char:

        spaces = [(m.end(), max_char - (m.end() + 1)) for m in re.finditer(r"\s", s) if
                         m.end() + 1 > max_char]
        if spaces:
            ins_idx = spaces[0][0]
        else:
            ins_idx = [(m.end(), max_char - (m.end() + 1)) for m in re.finditer(r"\s", s)][-1][0]
        new_s = s[:ins_idx] + "\n" + s[ins_idx:]

        return new_s
    else:
        return s

def top_chart(df: pd.DataFrame,
              date_start: str=None,
              date_end: str=None,
              chart_type: str="album",
              grid_size: tuple=(3,3),
              art_size: tuple=(500,500),
              tz="local") -> None:

    # default image
    img_default = Image.open(Path("static/missingno.jpg"))

    # datetime convert
    df[f"time_{tz}"] = pd.to_datetime(df[f"time_{tz}"])

    # num images and resolution
    num_squares = int(np.prod(grid_size))
    res_total = tuple(map(int, np.multiply(grid_size, art_size)))[::-1]

    # font
    font_ratio = 6e-6
    font = ImageFont.truetype("static/NotoSansTC-Regular.ttf", int(np.prod(res_total) * font_ratio))

    # filter by date end points
    date_start = pd.to_datetime(date_start) if date_start is not None else df[f"time_{tz}"].min()
    date_end = pd.to_datetime(date_end) if date_end is not None else df[f"time_{tz}"].max()
    # print(date_start, date_end)
    df = df[df[f"time_{tz}"].between(date_start, date_end)]

    # groupby and aggregate counts
    # merge with mbids
    # always used to merge
    # top counts one album per artist
    df_artist_album_counts = df.groupby(["artist", "album"]) \
                             .size() \
                             .reset_index(name="count_album") \
                             .sort_values("count_album", ascending=False) \
                             .iloc[:num_squares,:] \
                             .drop_duplicates(subset="artist")

    if chart_type == "album":
        df_counts = df.groupby(["artist", "album"]) \
                          .size() \
                          .reset_index(name="count") \
                          .sort_values("count", ascending=False) \
                          .iloc[:num_squares,:]
    elif chart_type == "artist":
        df_counts = df.groupby("artist") \
                          .size() \
                          .reset_index(name="count") \
                          .sort_values("count", ascending=False) \
                          .iloc[:num_squares,:] \
                          .merge(df_artist_album_counts, how="left", on="artist")
    elif chart_type == "track":
        df_counts = df.groupby(["artist", "album", "title"]) \
                          .size() \
                          .reset_index(name="count") \
                          .sort_values("count", ascending=False) \
                          .iloc[:num_squares,:]
    else:
        raise ValueError("chart_type must be one of {'album', 'artist', 'track'}")
    # load mbz cover ref data
    # filtered by mbids to lessen load
    df_mbid, covers_dict = load_covers(df=df_counts)
    print(df_counts)
    df_counts = df_counts.merge(df_mbid, on=["artist", "album"])

    # create grid
    chart_grid = Image.new('RGB', res_total)

    # load images
    # resize 'em
    squares = []
    for idx, row in df_counts.iterrows():
        print(row)
        artist = row.loc['artist']
        album = row.loc['album']
        track = row.loc['title'] if chart_type == "track" else None
        play_count = row.loc['count']
        mbid = row.loc['mbid']

        print(row['mbid'])
        try:
            img = Image.fromarray(covers_dict[mbid])
        except KeyError:
            img = deepcopy(img_default)

        # thumbnail resizing
        img = img.resize(art_size, Image.LANCZOS)

        # text overlay
        # add newlines for long album titles
        # calculate how many newlines are required
        max_char = 40  # magic number for now

        if chart_type == "album":
            artist_string = newline_name(artist, max_char)
            album_string = newline_name(album, max_char)

            draw = ImageDraw.Draw(img)
            draw.text((0,0), f"{artist_string}\n{album_string}\n{play_count}", stroke_width=1.5, stroke_fill=(0,0,0), font=font)
        elif chart_type == "artist":
            artist_string = newline_name(artist, max_char)

            draw = ImageDraw.Draw(img)
            draw.text((0, 0), f"{artist_string}\n{play_count}", stroke_width=1.5, stroke_fill=(0,0,0), font=font)
        elif chart_type == "track":
            artist_string = newline_name(artist, max_char)
            track_string = newline_name(track, max_char)

            draw = ImageDraw.Draw(img)
            draw.text((0, 0), f"{artist_string}\n{track_string}\n{play_count}", stroke_width=1.5, stroke_fill=(0,0,0), font=font)

        squares.append(img)

    # not enough albums to grid
    # fill with black
    if len(squares) < num_squares:
        squares += [Image.new('RGB', art_size)] * (num_squares - len(squares))

    # grid 'em
    squidx = 0
    for i in range(grid_size[0]):
        for j in range(grid_size[1]):
            chart_grid.paste(squares[squidx], (j * art_size[0], i * art_size[1]))
            squidx += 1
    chart_grid.show()

if __name__ == "__main__":
    # df_mbid, covers_dict = load_covers()
    top_chart(pd.read_csv("data/combined/combined.csv"), date_start="2025-02-01", chart_type="artist", grid_size=(6, 6))