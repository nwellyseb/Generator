from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests


@dataclass(frozen=True)
class CommonsAsset:
    download_url: str
    page_url: str
    creator_name: str
    license_name: str
    license_url: str
    width: int
    height: int
    file_extension: str
    title: str


def _plain(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extension_for(url: str, mime: str) -> str:
    mime = mime.lower().strip()
    if mime in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if mime == "image/png":
        return ".png"
    if mime == "image/webp":
        return ".webp"

    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    # SVG and TIFF originals are normally returned through a PNG/JPEG thumbnail.
    return ".png"


def _usable_dimensions(width: int, height: int) -> bool:
    if width <= 0 or height <= 0:
        return True
    longest = max(width, height)
    shortest = min(width, height)
    area = width * height
    # Portrait photos, old scans, and diagrams are all useful after FFmpeg crops
    # them. The old wide-only threshold rejected most of those assets.
    return (longest >= 480 and shortest >= 180) or area >= 220_000


def _asset_from_page(page: dict[str, object]) -> CommonsAsset | None:
    info_list = page.get("imageinfo") or []
    if not isinstance(info_list, list) or not info_list:
        return None
    info = info_list[0]
    if not isinstance(info, dict):
        return None

    original_mime = str(info.get("mime") or "").lower()
    thumb_mime = str(info.get("thumbmime") or "").lower()
    download_url = str(info.get("thumburl") or info.get("url") or "")
    page_url = str(info.get("descriptionurl") or "")
    if not download_url or not page_url:
        return None

    # Wikimedia returns raster thumbnails for SVGs and several other formats.
    # Judge the downloadable thumbnail rather than rejecting the original file.
    effective_mime = thumb_mime or original_mime
    allowed_originals = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/svg+xml",
        "image/tiff",
        "image/gif",
    }
    allowed_downloads = {"image/jpeg", "image/png", "image/webp", ""}
    if original_mime not in allowed_originals or effective_mime not in allowed_downloads:
        return None

    width = int(info.get("thumbwidth") or info.get("width") or 0)
    height = int(info.get("thumbheight") or info.get("height") or 0)
    if not _usable_dimensions(width, height):
        return None

    metadata = info.get("extmetadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    artist = _plain((metadata.get("Artist") or {}).get("value") if isinstance(metadata.get("Artist"), dict) else "")
    credit = _plain((metadata.get("Credit") or {}).get("value") if isinstance(metadata.get("Credit"), dict) else "")
    creator = artist or credit or "Unknown creator"
    license_name = _plain(
        (metadata.get("LicenseShortName") or {}).get("value")
        if isinstance(metadata.get("LicenseShortName"), dict)
        else ""
    ) or _plain(
        (metadata.get("UsageTerms") or {}).get("value")
        if isinstance(metadata.get("UsageTerms"), dict)
        else ""
    ) or "See source page"
    license_url = _plain(
        (metadata.get("LicenseUrl") or {}).get("value")
        if isinstance(metadata.get("LicenseUrl"), dict)
        else ""
    )

    return CommonsAsset(
        download_url=download_url,
        page_url=page_url,
        creator_name=creator,
        license_name=license_name,
        license_url=license_url,
        width=width,
        height=height,
        file_extension=_extension_for(download_url, effective_mime),
        title=str(page.get("title") or "Wikimedia Commons image"),
    )


def _asset_score(asset: CommonsAsset) -> float:
    area_score = math.log10(max(1, asset.width * asset.height))
    landscape_bonus = 0.8 if asset.width >= asset.height else 0.2
    known_license = 0.5 if asset.license_name != "See source page" else 0.0
    known_creator = 0.3 if asset.creator_name != "Unknown creator" else 0.0
    title = asset.title.lower()
    icon_penalty = 1.8 if any(word in title for word in (" icon", " logo", " emblem", " pictogram")) else 0.0
    return area_score + landscape_bonus + known_license + known_creator - icon_penalty


class WikimediaCommonsClient:
    endpoint = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.used_page_ids: set[int] = set()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "FreeDocumentaryGenerator/3.0 "
                    "(local video creator; preserves Wikimedia attribution and license metadata)"
                ),
                "Accept": "application/json",
            }
        )

    def _get_json(self, params: dict[str, object]) -> dict[str, object]:
        try:
            response = self.session.get(self.endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Wikimedia returned an unexpected response.")
            if payload.get("error"):
                raise RuntimeError(f"Wikimedia API error: {payload['error']}")
            return payload
        except requests.exceptions.SSLError as exc:
            raise RuntimeError(
                "Could not establish a secure connection to Wikimedia Commons. "
                "Check the Mac date/time, VPN, security software, or Python certificates."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                "Could not reach Wikimedia Commons. Check the internet connection, DNS, VPN, or firewall."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError("Wikimedia Commons timed out. Try the source test again.") from exc
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            raise RuntimeError(f"Wikimedia Commons returned HTTP {status}.") from exc
        except ValueError as exc:
            raise RuntimeError("Wikimedia Commons returned invalid JSON.") from exc

    def _search_pages(self, query: str) -> list[dict[str, object]]:
        base_params: dict[str, object] = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 30,
            "gsrsort": "relevance",
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata|thumbmime",
            "iiurlwidth": 1920,
            "iiextmetadatalanguage": "en",
            "iiextmetadatafilter": "Artist|Credit|LicenseShortName|LicenseUrl|UsageTerms",
            "format": "json",
            "formatversion": 2,
        }
        payload = self._get_json(base_params)
        pages = (payload.get("query") or {}).get("pages") if isinstance(payload.get("query"), dict) else []
        if isinstance(pages, list) and pages:
            return [page for page in pages if isinstance(page, dict)]

        # A title-biased second pass helps with proper names and acronyms such as
        # ELIZA, ENIAC, and AlphaGo, which full-text search can occasionally bury.
        title_payload = self._get_json({**base_params, "gsrsearch": f"intitle:{query}"})
        title_pages = (
            (title_payload.get("query") or {}).get("pages")
            if isinstance(title_payload.get("query"), dict)
            else []
        )
        return [page for page in title_pages if isinstance(page, dict)] if isinstance(title_pages, list) else []

    def search_image(self, query: str) -> CommonsAsset | None:
        pages = self._search_pages(query)
        candidates: list[tuple[float, int, CommonsAsset]] = []
        for page in pages:
            page_id = int(page.get("pageid") or 0)
            if not page_id or page_id in self.used_page_ids:
                continue
            asset = _asset_from_page(page)
            if asset is None:
                continue
            candidates.append((_asset_score(asset), page_id, asset))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        _, page_id, asset = candidates[0]
        self.used_page_ids.add(page_id)
        return asset

    def download(self, asset: CommonsAsset, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.session.get(asset.download_url, stream=True, timeout=180) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
        except requests.RequestException as exc:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"Could not download Wikimedia image: {asset.page_url}") from exc
        if not destination.exists() or destination.stat().st_size < 8_000:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"Wikimedia image download was empty or incomplete: {asset.page_url}")
