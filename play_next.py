#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
# "requests",
# ]
# ///
from __future__ import annotations

from common import Client, Episode, PlaylistItem, PlaylistItems
from logger import logger


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

    client.update_playlist(playlist["id"], new_items - existing_items, action="add")
    client.update_playlist(playlist["id"], existing_items - new_items, action="remove")


def main() -> None:
    c = Client()
    c.login()
    items = c.items[: c._config["playlist"]["count"]]
    update_playlist(c, items)


if __name__ == "__main__":
    main()
