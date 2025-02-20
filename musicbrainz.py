import musicbrainzngs as mbz
from typing import Tuple
import json
import pandas as pd
from jellyfish import levenshtein_distance as ldist
from helpers import css
import numpy as np
from tqdm import tqdm
from pathlib import Path
from PIL import Image
from io import BytesIO
from base64 import b64encode, b64decode
import h5py
# pd.set_option('display.max_rows', 500)
# pd.set_option('display.max_columns', 20)
# pd.set_option('display.width', 1000)

# musicbrainz API calling for album art (maybe durations too?)
# root_api_url = r"https://musicbrainz.org/ws/2/"
# https://musicbrainz.org/doc/MusicBrainz_API
# https://python-musicbrainzngs.readthedocs.io/en/v0.7.1/
# https://musicbrainz.org/doc/MusicBrainz_API/Search
app = "SoniCollecti"
version = "1.0"
mbz.set_useragent(app, version, contact="mjwander211@gmail.com")

def write_img_from_hdf5(release_id: str, file_name: str) -> None:
    file_path = Path("data/combined/mb_covers.h5")
    with h5py.File(file_path, 'r') as file:
        idx = np.where(file["mbid"][:] == release_id.encode())[0]
        img_data = file["covers"][idx][0]
    Image.fromarray(img_data).save(Path("data/images_testing") / f"{file_name}.jpg")

def write_hdf5_cover(release_id: str, cover_bytes: bytes, cover_size: tuple=(500,500)) -> None:
    file_path = Path("data/combined/mb_covers.h5")
    # entry_dict = {release_id: cover_bytes}
    # MUST RESIZE FOR STANDARDIZATION!
    img_data = np.asarray(Image.open(BytesIO(cover_bytes)).resize(cover_size, Image.LANCZOS))

    # I CAN'T BELIEVE GRAYSCALE IMAGES DESTROY THIS!
    if len(img_data.shape) == 2:
        print(img_data.shape)
        img_data = np.dstack([img_data]*3)

    if file_path.is_file():
        with h5py.File(file_path, 'r+') as file:
            # resizing
            # "appending"
            file["mbid"].resize((file["mbid"].shape[0] + 1), axis=0)
            file["mbid"][-1] = release_id

            file["covers"].resize(file["covers"].shape[0] + 1, axis=0)
            file["covers"][-1] = img_data

    else:
        # Create a new HDF5 file
        with h5py.File(file_path, "w") as file:
            # Create a dataset in the file
            # OPAQUE for binary, wrap in np.void()
            file.create_dataset("covers", shape=(1, *np.shape(img_data)), maxshape=(None, *np.shape(img_data)), dtype=h5py.h5t.STD_U8BE, data=img_data)
            file.create_dataset("mbid", shape=(1,), maxshape=(None,), dtype=h5py.string_dtype(length=36), data=release_id)


def mbz_get_release(artist: str, album: str) -> Tuple[dict, str]:
    # most confident search result
    # get mbz ID for later
    releases = mbz.search_releases(artist=artist, release=album)["release-list"]
    if not releases:
        print(f"Release not found in the Musicbrainz database: {artist} - {album}\n")
        return {}, ""

    # find first one with approved FRONT cover art
    # must match name of album and artist
    sim_thresh = 5
    for release in releases:
        # levenshtein distance on cleaned strings
        album_title = release["title"]
        # artist_names = set([ac["name"] for ac in release["artist-credit"]])

        if ldist(css(album), css(album_title)) <= sim_thresh:
            release_id = release["id"]
            try:
                image_list = mbz.get_image_list(release_id)["images"]
                if any([img["front"] for img in image_list]):
                    return release, release_id
            except mbz.musicbrainz.ResponseError:
                continue
    return {}, ""

def mbz_get_cover(release_id: str, cover_size: str="500") -> bytes:
    # cover_size == 250, 500, or 1200
    return mbz.get_image(mbid=release_id,
                         coverid="front",
                         size=cover_size,
                         entitytype="release")

def update_db_mbids(df: pd.DataFrame) -> None:
    file_dir = Path("data/combined")
    if not file_dir.is_dir():
        file_dir.mkdir()

    releases_file_path = file_dir / "mb_ids.csv"
    try:
        df_releases_logged = pd.read_csv(releases_file_path)
    except FileNotFoundError:
        df_releases_logged = pd.DataFrame(columns=["artist", "album", "mbid"])

    df_releases = df.groupby(["artist", "album"])[["artist", "album"]].size().reset_index().drop(0, axis=1)

    # merge to get non-logged values
    df_releases = pd.merge(df_releases, df_releases_logged, on=["artist", "album"], how="left", indicator="logged")
    df_releases["logged"] = np.where(df_releases["logged"] == 'both', True, False)

    # iterate over False "logged" values
    # don't reset index
    print(df_releases.columns)
    df_releases_tbl = df_releases[(~df_releases["logged"]) | (df_releases["mbid"].isna())].reset_index(drop=True)
    print(df_releases_tbl)
    if not df_releases_tbl.empty:
        for idx, row in tqdm(df_releases_tbl.loc[:, ["artist", "album", "logged"]].iterrows(), total=len(df_releases_tbl)):
            # print(idx)
            # ar_al = f"{row[0]} - {row[1]}"
            # print(ar_al)
            # if log_exists and (row[0] in df_releases_logged[""].values and row[1] in df_releases_logged["album"].values):
            #     print("Release already logged (string)")
            # else:
            release, release_id = mbz_get_release(row.iloc[0], row.iloc[1])
            df_releases_tbl.iloc[idx, list(df_releases_tbl.columns).index("mbid")] = release_id if release_id else np.nan

        # concat with those to-be-logged
        # write mbids.csv
        pd.concat((df_releases_logged.loc[:, ["artist", "album", "mbid"]],
                   df_releases_tbl.loc[:, ["artist", "album", "mbid"]])).reset_index(drop=True) \
                                                                        .drop_duplicates() \
                                                                        .sort_values(["artist", "album"]) \
                                                                        .reset_index(drop=True) \
                                                                        .to_csv(releases_file_path, index=False)

def update_db_covers() -> None:
    file_dir = Path("data/combined")
    releases_file_path = file_dir / "mb_ids.csv"
    if not releases_file_path.is_file():
        return
    df_mbids = set(pd.read_csv(releases_file_path).dropna().loc[:, "mbid"].values)

    covers_file_path = file_dir / "mb_covers.h5"
    if covers_file_path.is_file():
        with h5py.File(covers_file_path, 'r') as file:
            releases_logged = set(map(lambda s: s.decode(), file['mbid'][:]))
    else:
        releases_logged = set()

    # only get mbids which don't have logged covers to-be-downloaded
    covers_tbdl = df_mbids.difference(releases_logged)
    if covers_tbdl:
        for mbid in tqdm(covers_tbdl, total=len(covers_tbdl)):
            cover_bytes = mbz_get_cover(mbid)
            write_hdf5_cover(mbid, cover_bytes)

if __name__ == "__main__":
    update_db_mbids(pd.read_csv("data/combined/combined.csv"))
    update_db_covers()

    # cover image scrutiny and testing
    # df_mbid = pd.read_csv("data/combined/mb_ids.csv")
    # for idx, mbid in enumerate(df_mbid["mbid"].dropna()):
    #     write_img_from_hdf5(mbid, str(idx))