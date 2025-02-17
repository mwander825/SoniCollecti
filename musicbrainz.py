import musicbrainzngs as mbz
from typing import Tuple
import json
import pandas as pd
from PIL import Image
import io
import requests
import time
from tqdm import tqdm
from pathlib import Path

# musicbrainz API calling for album art (maybe durations too?)
# root_api_url = r"https://musicbrainz.org/ws/2/"
# https://musicbrainz.org/doc/MusicBrainz_API
# https://python-musicbrainzngs.readthedocs.io/en/v0.7.1/
# https://musicbrainz.org/doc/MusicBrainz_API/Search
app = "SoniCollecti"
version = "1.0"
mbz.set_useragent(app, version, contact="mjwander211@gmail.com")

def write_json(artist: str, album: str, release_id: str, cover_bytes: bytes) -> None:
    file_path = Path("data/mb_releases.json")
    entry_dict = {release_id: {"artist": artist,
                  "release": album,
                  "cover_bytes": str(cover_bytes)}}

    if file_path.is_file():
        with open(file_path, "r") as file:
            # update
            data = json.load(file)
            if release_id in set(data.keys()):
                print("Release already logged (id)")
                return
            else:
                data[release_id] = entry_dict[release_id]
        # separate overwrite step
        with open(file_path, "w") as file:
            json.dump(data, file)
    else:
        with open(file_path, "w") as file:
            # create
            json.dump(entry_dict, file)

def mbz_get_release(artist: str, album: str) -> Tuple[dict, str]:
    # most confident search result
    # get mbz ID for later
    releases = mbz.search_releases(artist=artist, release=album)["release-list"]
    if not releases:
        print(f"Release not found in the Musicbrainz database: {artist} - {album}\n")
        return {}, ""

    # find first one with approved FRONT cover art
    for release in releases:
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

def refresh_db(df: pd.DataFrame) -> None:
    file_path = Path("data/mb_releases.json")
    if file_path.is_file():
        with open(file_path, "r") as file:
            releases_logged = set([f"{v["artist"]} - {v["release"]}" for v in json.load(file).values()])
    else:
        releases_logged = {}
    df_release = df.groupby(["artist", "album"])[["artist", "album"]].size().reset_index().drop(0, axis=1)
    for idx, row in tqdm(df_release.iterrows(), total=len(df_release)):
        ar_al = f"{row[0]} - {row[1]}"
        print(ar_al)
        if ar_al in releases_logged:
            print("Release already logged (string)")
            continue
        release, release_id = mbz_get_release(row[0], row[1])
        if release and release_id:
            cover_bytes = mbz_get_cover(release_id)
            write_json(row[0], row[1], release_id, cover_bytes)

if __name__ == "__main__":
    # refresh_db(df)
    # release, release_id = mbz_get_release("Cassandra Jenkins", "My Light, My Destroyer")
    # cover_bytes = mbz_get_cover(release_id)
    # write_json("Cassandra Jenkins", "My Light, My Destroyer", release_id, cover_bytes)
    # image = Image.open(io.BytesIO(cover_bytes))