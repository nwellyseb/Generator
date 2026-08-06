"""Run manually: python tests/render_smoke_test.py"""
from pathlib import Path

from documentary_generator.media import concatenate_scenes, create_placeholder_card, render_scene
from documentary_generator.utils import run_command

root = Path(__file__).resolve().parents[1] / "outputs" / "smoke-test"
root.mkdir(parents=True, exist_ok=True)
image = root / "card.png"
audio = root / "tone.wav"
scene = root / "scene.mp4"
final = root / "joined.mp4"
create_placeholder_card("Render Test", "Synthetic audio, because even tests need narration.", image, (640, 360))
run_command(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(audio)])
render_scene(visual_path=image, audio_path=audio, output_path=scene, width=640, height=360, fps=24)
concatenate_scenes([scene, scene], final)
print(final)
