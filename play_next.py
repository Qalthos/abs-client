import requests


ABS_URL = ""
USERNAME = ""
PASSWORD = ""


def _sort_episodes(p) -> int:
    """Sort episodes by publish date."""
    return p["publishedAt"]


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

    def items(self):
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
                    items.append(episode)
                    continue
                if resp["userMediaProgress"]["isFinished"] is True:
                    continue

                items.append(episode)

        return items

    def update_playlist(self, items) -> None:
        resp = self.session.get(ABS_URL + "api/playlists").json()
        playlist_id = resp["playlists"][0]["id"]

        episodes = [
            {"libraryItemId": item["libraryItemId"], "episodeId": item["id"]}
            for item in items
        ]
        resp = self.session.patch(
            ABS_URL + f"api/playlists/{playlist_id}", params={"items": episodes}
        )


def main() -> None:
    c = Client()
    c.login()
    items = sorted(c.items(), key=_sort_episodes)
    c.update_playlist(items[:5])
    for item in items[:5]:
        podcast = item["audioFile"]["metaTags"]["tagAlbum"]
        title = item["title"]
        date = item["audioFile"]["metaTags"]["tagDate"]
        print(f"{date}\n{podcast} - {title}")


if __name__ == "__main__":
    main()
