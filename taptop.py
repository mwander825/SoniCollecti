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

feat_match = re.compile(r"(?i)(\(feat\..+\))|(\(with.+\))|(\(featuring.+\))")

def load_covers(df: pd.DataFrame=None, mbids: Iterable=None) -> Tuple[pd.DataFrame, dict]:
    file_path = Path("data/combined/release_covers.h5")
    df_mbid = pd.read_csv("data/combined/release_ids.csv")
    if df is not None:
        # assumedly filtered down a bit
        df_mbid = df_mbid.merge(df, on=['artist', 'album']).loc[:, ["artist", "album", "mbid"]].drop_duplicates()
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
    newline_tups = []

    # if the string is longer than the max allowed length (for fitting visually)
    if len(s) > max_char:
        split_s = s
        split_idx = 0  # the index of the last split found
        while (len(s) - split_idx) > max_char:

            # iterate find every space
            spaces = [m.end() for m in re.finditer(r"\s", split_s)]
            if spaces:
                # if spaces were found above, filter past the max char number (either first one or last one)
                # the first one is the split (\n)
                past_spaces = [space for space in spaces if space + 1 > (max_char + split_idx)]
                if past_spaces:
                    ins_idx = past_spaces[0]
                else:
                    ins_idx = spaces[-1]
            else:
                # if no spaces were found above, the first character after is the split (\n-)
                ins_idx = [m.end() for m in re.finditer(r".", split_s) if m.end() > (max_char + split_idx)][0]

            # list of splits to make
            newline_tups.append((ins_idx, "\n" if spaces else "\n-"))

            # the index of the current newest split
            split_idx = newline_tups[-1][0]

        # create new string by inserting delimeters for spacing
        for ii, d in newline_tups:
            if d == "\n":
                split_s = split_s[:ii - 1] + d + split_s[ii:]
            else:
                split_s = split_s[:ii] + d + split_s[ii:]
        return split_s
    else:
        return s

def top_chart(df: pd.DataFrame,
              date_start: str=None,
              date_end: str=None,
              chart_type: str="album",
              grid_size: tuple=(3,3),
              art_size: tuple=(500,500),
              tz="local") -> None:

    # lower chart_type (just in case...)
    chart_type = chart_type.lower()

    # lower timezone (just in case...)
    tz = tz.lower()

    # default image
    img_default = Image.open(Path("static/missingno.jpg"))

    # datetime convert
    df[f"time_{tz}"] = pd.to_datetime(df[f"time_{tz}"])

    # num images and resolution
    num_squares = int(np.prod(grid_size))
    res_total = tuple(map(int, np.multiply(grid_size, art_size)))[::-1]

    # font
    # font_ratio = 6e-6
    # print(int(np.prod(res_total) * font_ratio))
    # font = ImageFont.truetype("static/NotoSansTC-Regular.ttf", int(np.prod(res_total) * font_ratio))
    # 0.4
    font_size = 40
    # print(font_size)
    font = ImageFont.truetype("static/NotoSansTC-Regular.ttf", font_size)
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
                             .drop_duplicates(subset="artist")


    if chart_type == "album":
        df_counts = df.groupby(["artist", "album"]) \
                          .size() \
                          .reset_index(name="count") \
                          .sort_values("count", ascending=False) \
                          .iloc[:num_squares + 1,:]
    elif chart_type == "artist":
        df_counts = df.groupby("artist") \
                          .size() \
                          .reset_index(name="count") \
                          .sort_values("count", ascending=False) \
                          .iloc[:num_squares + 1,:] \
                          .merge(df_artist_album_counts, how="left", on="artist")
    elif chart_type == "track":
        df_counts = df.groupby(["artist", "album", "title"]) \
                          .size() \
                          .reset_index(name="count") \
                          .sort_values("count", ascending=False) \
                          .iloc[:num_squares + 1,:]
    else:
        raise ValueError("chart_type must be one of {'album', 'artist', 'track'}")
    # load mbz cover ref data
    # filtered by mbids to lessen load
    df_mbid, covers_dict = load_covers(df=df_counts)
    # print(df_counts)
    df_counts = df_counts.merge(df_mbid, on=["artist", "album"])
    # print(df_mbid)
    # print(df_counts)

    # create grid
    chart_grid = Image.new('RGB', res_total)

    # load images
    # resize 'em
    squares = []
    for idx, row in df_counts.iterrows():
        artist = row.loc['artist']
        album = row.loc['album']
        track = row.loc['title'] if chart_type == "track" else None
        play_count = row.loc['count']
        mbid = row.loc['mbid']

        try:
            img = Image.fromarray(covers_dict[mbid])
        except KeyError:
            img = deepcopy(img_default)

        # thumbnail resizing
        img = img.resize(art_size, Image.LANCZOS)

        # text overlay
        # add newlines for long album titles
        # calculate how many newlines are required
        max_char = 24  # magic number for now

        if chart_type == "album":
            artist_string = newline_name(artist, max_char)
            album_string = newline_name(album, max_char)

            draw = ImageDraw.Draw(img)
            draw.text((0,0), f"{artist_string}\n{album_string}\n({play_count})", stroke_width=5, stroke_fill=(0,0,0), font=font)
        elif chart_type == "artist":
            artist_string = newline_name(artist, max_char)

            draw = ImageDraw.Draw(img)
            draw.text((0, 0), f"{artist_string}\n({play_count})", stroke_width=5, stroke_fill=(0,0,0), font=font)
        elif chart_type == "track":
            artist_string = newline_name(artist, max_char)
            track_string = newline_name(feat_match.sub('', track).strip(), max_char)

            draw = ImageDraw.Draw(img)
            draw.text((0, 0), f"{artist_string}\n{track_string}\n({play_count})", stroke_width=5, stroke_fill=(0,0,0), font=font)

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
    # df = pd.read_csv("data/combined/combined.csv")
    top_chart(pd.read_csv("data/combined/combined.csv"),
              date_start="2025-04-01",
              date_end="2025-04-30",
              chart_type="album", grid_size=(6,6))