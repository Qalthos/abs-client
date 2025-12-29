#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
# "requests",
# ]
# ///
from __future__ import annotations

from common import Client, Episode, PlaylistItem, PlaylistItems


def update_playlist(client: Client) -> None:
    client.cleanup()

    playlist = client.get_playlist()

    existing_items = PlaylistItems.from_json(playlist)

    episodes = client.items[: client._config["playlist"]["count"]]
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
    update_playlist(c)


if __name__ == "__main__":
    main()
