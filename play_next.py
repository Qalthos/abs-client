#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
# "requests",
# ]
# ///
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from common import Client, Episode
from logger import logger

if TYPE_CHECKING:
    from typing import Self


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


def update_playlist(client: Client, episodes: list[Episode]) -> None:
    resp = client.session.get(client.url + "api/playlists").json()

    try:
        playlist = next(
            p
            for p in resp["playlists"]
            if p["name"] == client._config["playlist"]["name"]
        )
    except StopIteration:
        logger.warning("Playlist not found, creating")
        resp = client.session.post(
            client.url + "api/playlists",
            data={
                "libraryId": client.library,
                "name": "Up Next",
            },
        ).json()
        playlist = resp

    existing_items = PlaylistItems.from_json(playlist)

    new_items = PlaylistItems(
        items=[
            PlaylistItem(
                episode_id=episode.id,
                library_id=episode.library_id,
                episode_name=episode.name,
            )
            for episode in episodes
        ]
    )
    net_new = new_items - existing_items
    net_old = existing_items - new_items

    # Add new items
    payload = net_new.to_json()
    for item in net_new.items:
        logger.info("Adding %s", item.episode_name)
    resp = client.session.post(
        client.url + f"api/playlists/{playlist['id']}/batch/add",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    # Remove stale items
    payload = net_old.to_json()
    for item in net_old.items:
        logger.info("Removing %s", item.episode_name)
    resp = client.session.post(
        client.url + f"api/playlists/{playlist['id']}/batch/remove",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )


def main() -> None:
    c = Client()
    c.login()
    items = c.items[: c._config["playlist"]["count"]]
    update_playlist(c, items)


if __name__ == "__main__":
    main()
