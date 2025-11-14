from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import time
from typing import TYPE_CHECKING

import requests
import tomllib
from pathlib import Path

from logger import logger


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

    def __repr__(self) -> str:
        return f"{self.podcast} - {self.name}"


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
        start = time.monotonic()
        resp = self.session.get(self.url + f"api/libraries/{self.library}/items").json()
        podcast_ids: list[str] = [podcast["id"] for podcast in resp["results"]]

        items: list[Episode] = []
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
                if (
                    resp["userMediaProgress"] is not None
                    and resp["userMediaProgress"]["isFinished"] is True
                ):
                    continue

                items.append(Episode.from_json(episode))

        all_episodes = sorted(items, key=lambda i: i.publish_ts)
        duration = time.monotonic() - start
        logger.debug(f"Reading episodes took {duration:.2f} seconds")

        to_skip: int = self._config.get("playlist", {}).get("skip", 0)
        for episode in all_episodes[:to_skip]:
            logger.debug("Skipping %r", episode)

        return all_episodes[to_skip:]
