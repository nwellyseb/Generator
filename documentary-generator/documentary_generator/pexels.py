from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass(frozen=True)
class PexelsAsset:
    kind: str
    download_url: str
    page_url: str
    creator_name: str
    creator_url: str
    width: int
    height: int


class PexelsClient:
    video_endpoint = "https://api.pexels.com/v1/videos/search"
    photo_endpoint = "https://api.pexels.com/v1/search"

    def __init__(self, api_key: str, timeout: int = 30) -> None:
        if not api_key.strip():
            raise ValueError("A Pexels API key is required.")
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.used_video_ids: set[int] = set()
        self.used_photo_ids: set[int] = set()
        self.session = requests.Session()
        self.session.headers.update({"Authorization": self.api_key, "User-Agent": "FreeDocumentaryGenerator/3.0"})

    def _check(self, response: requests.Response) -> None:
        if response.status_code == 401:
            raise RuntimeError("Pexels rejected the API key.")
        if response.status_code == 429:
            raise RuntimeError("Pexels rate limit reached. Try again after the quota resets.")
        response.raise_for_status()

    def validate_key(self) -> None:
        try:
            response = self.session.get(
                self.photo_endpoint,
                params={"query": "nature", "per_page": 1},
                timeout=self.timeout,
            )
            self._check(response)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError("Could not reach Pexels. Check the internet connection, DNS, VPN, or firewall.") from exc
        except requests.exceptions.SSLError as exc:
            raise RuntimeError("Could not establish a secure connection to Pexels.") from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError("Pexels timed out.") from exc

    def search_video(self, query: str) -> PexelsAsset | None:
        response = self.session.get(
            self.video_endpoint,
            params={
                "query": query,
                "orientation": "landscape",
                "per_page": 20,
            },
            timeout=self.timeout,
        )
        self._check(response)

        candidates = response.json().get("videos", [])
        for video in candidates:
            video_id = int(video.get("id", 0))
            if not video_id or video_id in self.used_video_ids:
                continue
            files = [
                item
                for item in video.get("video_files", [])
                if item.get("file_type") == "video/mp4"
                and int(item.get("width") or 0) >= 640
                and int(item.get("height") or 0) >= 360
            ]
            if not files:
                continue
            files.sort(
                key=lambda item: (
                    abs(int(item.get("width") or 0) - 1280),
                    abs(int(item.get("height") or 0) - 720),
                )
            )
            chosen = files[0]
            self.used_video_ids.add(video_id)
            user = video.get("user") or {}
            return PexelsAsset(
                kind="video",
                download_url=str(chosen["link"]),
                page_url=str(video.get("url") or "https://www.pexels.com"),
                creator_name=str(user.get("name") or "Unknown creator"),
                creator_url=str(user.get("url") or "https://www.pexels.com"),
                width=int(chosen.get("width") or 0),
                height=int(chosen.get("height") or 0),
            )
        return None

    def search_photo(self, query: str) -> PexelsAsset | None:
        response = self.session.get(
            self.photo_endpoint,
            params={
                "query": query,
                "orientation": "landscape",
                "size": "large",
                "per_page": 20,
            },
            timeout=self.timeout,
        )
        self._check(response)

        for photo in response.json().get("photos", []):
            photo_id = int(photo.get("id", 0))
            if not photo_id or photo_id in self.used_photo_ids:
                continue
            src = photo.get("src") or {}
            url = src.get("large2x") or src.get("large") or src.get("original")
            if not url:
                continue
            self.used_photo_ids.add(photo_id)
            return PexelsAsset(
                kind="photo",
                download_url=str(url),
                page_url=str(photo.get("url") or "https://www.pexels.com"),
                creator_name=str(photo.get("photographer") or "Unknown creator"),
                creator_url=str(photo.get("photographer_url") or "https://www.pexels.com"),
                width=int(photo.get("width") or 0),
                height=int(photo.get("height") or 0),
            )
        return None

    def download(self, asset: PexelsAsset, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Do not forward the private API key to the CDN download host.
            with requests.get(
                asset.download_url,
                headers={"User-Agent": "FreeDocumentaryGenerator/3.0"},
                stream=True,
                timeout=180,
            ) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
        except requests.RequestException as exc:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"Could not download Pexels {asset.kind}: {asset.page_url}") from exc
        if not destination.exists() or destination.stat().st_size < 8_000:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"Pexels download was empty or incomplete: {asset.page_url}")
