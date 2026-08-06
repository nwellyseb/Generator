from pathlib import Path

from documentary_generator.models import DocumentaryPlan, Scene
from documentary_generator.text import split_manual_script, write_srt


def test_manual_script_split() -> None:
    plan = split_manual_script("First scene.\n\nSecond scene.", "A Topic")
    assert plan.title == "A Topic"
    assert len(plan.scenes) == 2


def test_srt_generation(tmp_path: Path) -> None:
    plan = DocumentaryPlan(
        title="Test",
        scenes=[Scene(narration="This is a short test sentence for captions.", visual_query="test")],
    )
    output = tmp_path / "captions.srt"
    write_srt(plan, [4.0], output)
    text = output.read_text(encoding="utf-8")
    assert "00:00:00,000 -->" in text
    assert "short test sentence" in text
