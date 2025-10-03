from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import requests


if TYPE_CHECKING:
    from typing import Self

ABS_URL = ""
USERNAME = ""
PASSWORD = ""


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

            episodes = resp["media"]["episodes"]

            for episode in episodes:
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
