from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cached_property
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
    podcast_id: str

    podcast: str
    name: str
    duration: float
    publish_ts: float

    @classmethod
    def from_json(cls, json, podcast_id: str, podcast_name: str) -> Self:
        return cls(
            id=json["id"],
            library_id=json["libraryItemId"],
            podcast_id=podcast_id,
            podcast=podcast_name,
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

    def cleanup(self, older_than: timedelta = timedelta(days=30)) -> None:
        cutoff = (datetime.now() - older_than).timestamp()
        for episode in self._all_episodes:
            if episode.publish_ts < cutoff and self._is_finished(episode):
                logger.info("Deleting %s", episode.name)
                self.session.delete(
                    self.url
                    + f"api/podcasts/{episode.podcast_id}/episode/{episode.id}",
                    params={"hard": 1},
                )

    @property
    def url(self) -> str:
        return self._config["audiobookshelf"]["url"]

    @property
    def items(self) -> list[Episode]:
        start = time.monotonic()
        all_episodes = self._all_episodes

        unfinished = [
            episode for episode in all_episodes if not self._is_finished(episode)
        ]

        duration = time.monotonic() - start
        logger.debug(f"Reading episodes took {duration:.2f} seconds")

        to_skip: int = self._config.get("playlist", {}).get("skip", 0)
        for episode in unfinished[:to_skip]:
            logger.debug("Skipping %r", episode)

        return unfinished[to_skip:]

    @cached_property
    def _all_episodes(self) -> list[Episode]:
        resp = self.session.get(self.url + f"api/libraries/{self.library}/items").json()
        podcast_ids: list[str] = [podcast["id"] for podcast in resp["results"]]

        items: list[Episode] = []
        for podcast in podcast_ids:
            resp = self.session.get(self.url + f"api/items/{podcast}").json()
            podcast_name = resp["media"]["metadata"]["title"]

            # Skip backlogged podcasts.
            if "backlog" in resp["media"]["tags"]:
                continue

            episodes = resp["media"]["episodes"]

            items.extend(
                Episode.from_json(
                    episode, podcast_id=podcast, podcast_name=podcast_name
                )
                for episode in episodes
            )

        return sorted(items, key=lambda i: i.publish_ts)

    def _is_finished(self, episode: Episode) -> bool:
        resp = self.session.get(
            self.url + f"api/items/{episode.podcast_id}",
            params={
                "expanded": 1,
                "include": "progress",
                "episode": episode.id,
            },
        )
        try:
            resp = resp.json()
        except requests.exceptions.JSONDecodeError:
            logger.exception(resp.content)
        return (
            resp["userMediaProgress"] is not None
            and resp["userMediaProgress"]["isFinished"] is True
        )
