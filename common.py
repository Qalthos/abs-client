from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cache, cached_property
import json
import time
from typing import TYPE_CHECKING

import requests
import tomllib
from pathlib import Path

from logger import logger


if TYPE_CHECKING:
    from typing import Self, Literal


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

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __str__(self) -> str:
        return f"  {self.date}\n{self.podcast}\t{self.name}"

    def __repr__(self) -> str:
        return f"{self.podcast} - {self.name}"


@dataclass
class PlaylistItem:
    episode_id: str
    library_id: str
    episode_name: str

    @classmethod
    def from_json(cls, json) -> Self:
        return cls(
            episode_id=json["episodeId"],
            library_id=json["libraryItemId"],
            episode_name=json["episode"]["title"],
        )

    def to_json(self) -> dict[str, str]:
        return {"episodeId": self.episode_id, "libraryItemId": self.library_id}

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented

        return (
            self.episode_id == other.episode_id and self.library_id == other.library_id
        )


@dataclass
class PlaylistItems:
    items: list[PlaylistItem]

    @classmethod
    def from_json(cls, json) -> PlaylistItems:
        items = [PlaylistItem.from_json(item) for item in json["items"]]
        return cls(items)

    def to_json(self) -> dict[str, list[dict[str, str]]]:
        return {"items": [item.to_json() for item in self.items]}

    def __sub__(self, other: PlaylistItems) -> PlaylistItems:
        items = list(self.items)
        for item in other.items:
            if item in items:
                items.remove(item)
        return self.__class__(items)


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

    def cleanup(self, older_than: timedelta = timedelta(days=30)) -> None:
        cutoff = (datetime.now() - older_than).timestamp()
        for episode in self.all_episodes:
            if episode.publish_ts < cutoff and self._is_finished(episode):
                logger.info("Deleting %s", episode.name)
                self.session.delete(
                    self.url
                    + f"api/podcasts/{episode.podcast_id}/episode/{episode.id}",
                    params={"hard": 1},
                )

    def update_playlist(
        self,
        playlist_id: str,
        episodes: PlaylistItems,
        action: Literal["add", "remove"],
    ) -> None:
        for item in episodes.items:
            logger.info("%s %s", action, item.episode_name)

        _resp = self.session.post(
            self.url + f"api/playlists/{playlist_id}/batch/{action}",
            data=json.dumps(episodes.to_json()),
            headers={"Content-Type": "application/json"},
        )

    @property
    def items(self) -> list[Episode]:
        start = time.monotonic()
        all_episodes = self.all_episodes

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
    def all_episodes(self) -> list[Episode]:
        resp = self.session.get(self.url + f"api/libraries/{self.library}/items").json()
        podcast_ids: list[str] = [podcast["id"] for podcast in resp["results"]]

        items: list[Episode] = []
        for podcast in podcast_ids:
            resp = self.session.get(self.url + f"api/items/{podcast}").json()

            # Skip backlogged podcasts.
            if "backlog" in resp["media"]["tags"]:
                continue

            podcast_name = resp["media"]["metadata"]["title"]
            episodes = resp["media"]["episodes"]

            items.extend(
                Episode.from_json(
                    episode, podcast_id=podcast, podcast_name=podcast_name
                )
                for episode in episodes
            )

        return sorted(items, key=lambda i: i.publish_ts)

    def _is_finished(self, episode: Episode) -> bool:
        try:
            json = self._episode_details(episode)
        except requests.exceptions.JSONDecodeError as exc:
            logger.exception(exc)
            return False

        return (
            json["userMediaProgress"] is not None
            and json["userMediaProgress"]["isFinished"] is True
        )

    def remaining(self, episode: Episode) -> float:
        try:
            json = self._episode_details(episode)
        except requests.exceptions.JSONDecodeError as exc:
            logger.exception(exc)
            return 0

        if json["userMediaProgress"] is None:
            return duration
        if json["userMediaProgress"]["isFinished"] is True:
            return 0
        return episode.duration - json["userMediaProgress"]["currentTime"]

    @cache
    def _episode_details(self, episode: Episode):
        return self.session.get(
            f"{self.url}api/items/{episode.podcast_id}",
            params={
                "expanded": 1,
                "include": "progress",
                "episode": episode.id,
            },
        ).json()
        )
        return (
            json["userMediaProgress"] is not None
            and json["userMediaProgress"]["isFinished"] is True
        )
