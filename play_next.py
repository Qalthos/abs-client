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


@dataclass
class PlaylistItem:
    episode_id: str
    library_id: str

    @classmethod
    def from_json(cls, json) -> Self:
        return cls(episode_id=json["episodeId"], library_id=json["libraryItemId"])

    def to_json(self) -> dict[str, str]:
        return {"episodeId": self.episode_id, "libraryItemId": self.library_id}

    def __eq__(self, other: Self) -> bool:
        return (
            self.episode_id == other.episode_id and self.library_id == other.library_id
        )


@dataclass
class PlaylistItems:
    items: list[PlaylistItem]

    @classmethod
    def from_json(cls, json) -> Self:
        items = [PlaylistItem.from_json(item) for item in json["items"]]
        return cls(items)

    def to_json(self) -> dict[str, list[dict[str, str]]]:
        return {"items": [item.to_json() for item in self.items]}

    def __sub__(self, other: Self) -> Self:
        items = list(self.items)
        for item in other.items:
            if item in items:
                items.remove(item)
        return self.__class__(items)


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

    @property
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

        return sorted(items, key=lambda i: i.publish_ts)

    def update_playlist(self, episodes: list[Episode]) -> None:
        resp = self.session.get(ABS_URL + "api/playlists").json()
        # TODO: Actually look for "Up Next"
        playlist = resp["playlists"][0]

        existing_items = PlaylistItems.from_json(playlist)

        new_items = PlaylistItems(
            items=[
                PlaylistItem(episode_id=episode.id, library_id=episode.library_id)
                for episode in episodes
            ]
        )
        net_new = new_items - existing_items
        net_old = existing_items - new_items

        # Add new items
        payload = net_new.to_json()
        resp = self.session.post(
            ABS_URL + f"api/playlists/{playlist['id']}/batch/add",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        # Remove stale items
        payload = net_old.to_json()
        resp = self.session.post(
            ABS_URL + f"api/playlists/{playlist['id']}/batch/remove",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        # PATCH replace
        # payload = new_items.to_json()
        # resp = self.session.patch(
        #     ABS_URL + f"api/playlists/{playlist['id']}",
        #     data=json.dumps(payload),
        #     headers={"Content-Type": "application/json"},
        # )


def main() -> None:
    c = Client()
    c.login()
    items = c.items
    c.update_playlist(items[:5])
    for item in items[:5]:
        print(item)


if __name__ == "__main__":
    main()
