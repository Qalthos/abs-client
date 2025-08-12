#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
# "requests",
# ]
# ///
from dataclasses import dataclass
from datetime import datetime
from typing import Self
import json

import requests


ABS_URL = ""
USERNAME = ""
PASSWORD = ""


@dataclass
class Episode:
    id: str
    library_id: str

    podcast: str
    name: str
    publish_ts: int

    @classmethod
    def from_json(cls, json) -> Self:
        return cls(
            id=json["id"],
            library_id=json["libraryItemId"],
            podcast=json["audioFile"]["metaTags"]["tagAlbum"],
            name=json["title"],
            publish_ts=json["publishedAt"],
        )

    @property
    def date(self) -> str:
        return datetime.fromtimestamp(self.publish_ts / 1000).date().isoformat()

    def __str__(self) -> str:
        return f"  {self.date}\n{self.podcast}\t{self.name}"


class Client:
    library: str

    def __init__(self) -> None:
        self.session = requests.Session()

    def login(self) -> None:
        resp = self.session.post(
            ABS_URL + "login", {"username": USERNAME, "password": PASSWORD}
        ).json()
        self.session.headers["Authorization"] = f"Bearer {resp['user']['token']}"

        self.library = resp["userDefaultLibraryId"]

    def items(self) -> list[Episode]:
        resp = self.session.get(ABS_URL + f"api/libraries/{self.library}/items").json()
        podcast_ids: list[str] = [podcast["id"] for podcast in resp["results"]]

        items = []
        for podcast in podcast_ids:
            resp = self.session.get(ABS_URL + f"api/items/{podcast}").json()

            # Skip backlogged podcasts.
            if "backlog" in resp["media"]["tags"]:
                continue

            episondes = resp["media"]["episodes"]

            for episode in episondes:
                resp = self.session.get(
                    ABS_URL + f"api/items/{podcast}",
                    params={
                        "expanded": 1,
                        "include": "progress",
                        "episode": episode["id"],
                    },
                ).json()
                if resp["userMediaProgress"] is None:
                    items.append(Episode.from_json(episode))
                    continue
                if resp["userMediaProgress"]["isFinished"] is True:
                    continue

                items.append(Episode.from_json(episode))

        return items

    def update_playlist(self, episodes: list[Episode]) -> None:
        resp = self.session.get(ABS_URL + "api/playlists").json()
        playlist = resp["playlists"][0]

        items = [
            {"libraryItemId": episode.library_id, "episodeId": episode.id}
            for episode in episodes
        ]
        payload = {"items": items}
        resp = self.session.post(
            ABS_URL + f"api/playlists/{playlist['id']}/batch/add",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )


def _sort_episodes(episode: Episode) -> int:
    """Sort episodes by publish date."""
    return episode.publish_ts


def main() -> None:
    c = Client()
    c.login()
    items = sorted(c.items(), key=_sort_episodes)
    c.update_playlist(items[:5])
    for item in items[:5]:
        print(item)


if __name__ == "__main__":
    main()
