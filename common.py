from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import requests
import tomllib
from pathlib import Path


if TYPE_CHECKING:
    from typing import Self


@dataclass
class Episode:
    id: str
    library_id: str

    podcast: str
    name: str
    duration: float
    publish_ts: float

    @classmethod
    def from_json(cls, json) -> Self:
        return cls(
            id=json["id"],
            library_id=json["libraryItemId"],
            podcast=json["audioFile"]["metaTags"]["tagAlbum"],
            name=json["title"],
            duration=json["audioFile"]["duration"],
            publish_ts=json["publishedAt"] / 1000,
        )

    @property
    def date(self) -> str:
        return datetime.fromtimestamp(self.publish_ts).date().isoformat()

    def __str__(self) -> str:
        return f"  {self.date}\n{self.podcast}\t{self.name}"


class Client:
    library: str

    def __init__(self) -> None:
        self.session = requests.Session()

        with Path("config.toml").open("rb") as config:
            self._config = tomllib.load(config)

    def login(self) -> None:
        resp = self.session.post(
            f"{self.url}login",
            {
                "username": self._config["audiobookshelf"]["user"],
                "password": self._config["audiobookshelf"]["password"],
            },
        ).json()
        self.session.headers["Authorization"] = f"Bearer {resp['user']['token']}"

        self.library = resp["userDefaultLibraryId"]

    @property
    def url(self) -> str:
        return self._config["audiobookshelf"]["url"]

    @property
    def items(self) -> list[Episode]:
        resp = self.session.get(self.url + f"api/libraries/{self.library}/items").json()
        podcast_ids: list[str] = [podcast["id"] for podcast in resp["results"]]

        items = []
        for podcast in podcast_ids:
            resp = self.session.get(self.url + f"api/items/{podcast}").json()

            # Skip backlogged podcasts.
            if "backlog" in resp["media"]["tags"]:
                continue

            episodes = resp["media"]["episodes"]

            for episode in episodes:
                resp = self.session.get(
                    self.url + f"api/items/{podcast}",
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

        return sorted(items, key=lambda i: i.publish_ts)[
            self._config["playlist"]["skip"] :
        ]
