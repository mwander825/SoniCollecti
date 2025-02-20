from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
import numpy as np
import pandas as pd
from typing import Tuple
from pathlib import Path
import re
import json
from copy import deepcopy
import h5py
# Inspired by https://www.tapmusic.net/

def data_load() -> Tuple[pd.DataFrame, dict]:
    file_path = Path("data/combined/mb_covers.h5")
    with h5py.File(file_path, 'r') as file:
        covers_dict = {k.decode():v for k,v in zip(file["mbid"][:], file["covers"][:])}

    df_mbid = pd.read_csv("data/combined/mb_ids.csv")

    return df_mbid, covers_dict

def top_chart(df: pd.DataFrame,
              date_start: str=None,
              date_end: str=None,
              grid_size: tuple=(3,3),
              art_size: tuple=(500,500),
              tz="local") -> None:
    # default image
    img_default = Image.open(Path("static/missingno.jpg"))

    # font
    font_ratio = 0.05
    font = ImageFont.truetype("static/Roboto-Regular.ttf", art_size[0] * font_ratio)

    # datetime convert
    df[f"time_{tz}"] = pd.to_datetime(df[f"time_{tz}"])

    # num images and resolution
    num_squares = int(np.prod(grid_size))
    res_total = tuple(map(int, np.multiply(grid_size, art_size)))

    # load mbz cover ref data
    df_mbid, covers_dict = data_load()

    # filter by date end points
    date_start = pd.to_datetime(date_start) if date_start is not None else df[f"time_{tz}"].min()
    date_end = pd.to_datetime(date_end) if date_end is not None else df[f"time_{tz}"].max()
    print(date_start, date_end)
    df = df[df[f"time_{tz}"].between(date_start, date_end)]

    # groupby and aggregate counts
    # merge with mbids
    df_album_counts = df.groupby(["artist", "album"])[["artist", "album"]] \
                      .size() \
                      .reset_index(name="count") \
                      .merge(df_mbid, on=["artist", "album"]) \
                      .sort_values("count", ascending=False) \
                      .iloc[:num_squares,:]
    # create grid
    chart_grid = Image.new('RGB', res_total)

    # load images
    # resize 'em
    squares = []
    for idx, row in df_album_counts.iterrows():
        artist = row.iloc[0]
        album = row.iloc[1]
        play_count = row.iloc[2]
        mbid = row.iloc[3]
        try:
            img = Image.fromarray(covers_dict[mbid])
        except KeyError:
            img = deepcopy(img_default)

        # thumbnail resizing (if larger)
        img.thumbnail(art_size)

        # text overlay
        # add newlines for long album titles
        # calculate how many newlines are required
        # 0.05 * x_width = max x chars
        artist_string = artist
        album_string = album
        max_char = int(0.05 * art_size[0])
        # for now
        if len(artist) > max_char:
            spaces_artist = [(m.end(), max_char - (m.end() + 1)) for m in re.finditer(r"\s", artist_string) if m.end() + 1 > max_char]
            ins_idx_artist = spaces_artist[0][0]
            artist_string = artist_string[:ins_idx_artist] + "\n" + artist_string[ins_idx_artist:]
        if len(album) > max_char:
            spaces_album = [(m.end(), max_char - (m.end() + 1)) for m in re.finditer(r"\s", album_string) if m.end() + 1 > max_char]
            ins_idx_album = spaces_album[0][0]
            album_string = album_string[:ins_idx_album] + "\n" + album_string[ins_idx_album:]
            print(album_string)
        draw = ImageDraw.Draw(img)
        draw.text((0,0), f"{artist_string}\n{album_string}\n{play_count}", stroke_width=1.5, stroke_fill=(0,0,0), font=font)

        squares.append(img)

    # grid 'em
    i = 0
    for row in range(grid_size[0]):
        for col in range(grid_size[1]):
            chart_grid.paste(squares[i], (col * art_size[0], row * art_size[1]))
            i += 1
            #y += thumbnail_height
        #x += thumbnail_width
        #y = 0
    chart_grid.show()

if __name__ == "__main__":
    df_mbid, covers_dict = data_load()
    top_chart(pd.read_csv("data/combined/combined.csv"), date_start="2025-01-01", date_end="2025-01-31", grid_size=(4,4))