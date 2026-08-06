from documentary_generator.commons import _asset_from_page
from documentary_generator.pipeline import _query_candidates


def test_query_candidates_extracts_proper_name() -> None:
    candidates = _query_candidates(
        "Screenshot of ELIZA interface conceptual visualization",
        "How AI learned to code",
        narration="ELIZA was an early conversational computer program.",
        on_screen_text="ELIZA, 1966",
    )
    lowered = [item.lower() for item in candidates]
    assert "eliza" in lowered
    assert any(item in lowered for item in ("computer history", "computer programming"))


def test_commons_accepts_svg_thumbnail() -> None:
    page = {
        "pageid": 42,
        "title": "File:Example computing diagram.svg",
        "imageinfo": [
            {
                "mime": "image/svg+xml",
                "thumbmime": "image/png",
                "thumburl": "https://upload.wikimedia.org/example/1920px-example.svg.png",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example.svg",
                "thumbwidth": 1200,
                "thumbheight": 800,
                "extmetadata": {
                    "Artist": {"value": "Example Creator"},
                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                },
            }
        ],
    }
    asset = _asset_from_page(page)
    assert asset is not None
    assert asset.file_extension == ".png"
    assert asset.width == 1200


def test_commons_accepts_portrait_historical_photo() -> None:
    page = {
        "pageid": 43,
        "title": "File:Early programmer portrait.jpg",
        "imageinfo": [
            {
                "mime": "image/jpeg",
                "thumbmime": "image/jpeg",
                "thumburl": "https://upload.wikimedia.org/example/portrait.jpg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Portrait.jpg",
                "thumbwidth": 640,
                "thumbheight": 1000,
                "extmetadata": {},
            }
        ],
    }
    asset = _asset_from_page(page)
    assert asset is not None
    assert asset.file_extension == ".jpg"
