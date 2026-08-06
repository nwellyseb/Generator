# Free Local Documentary Generator 4

Version 4 adds natural local narration with **Kokoro-82M**, while retaining the real-media search, captions, credits, and FFmpeg renderer from version 3.

## What changed

- Kokoro is the default narrator.
- Voice preview before a full render.
- Documentary delivery speed defaults to `0.92`.
- Sentences are bundled into natural breath groups instead of being read as one enormous paragraph or dozens of tiny robotic clips.
- Thought-group and paragraph pauses are adjustable.
- Narration is normalized to approximately `-16 LUFS` and checked for silence, clipping, and digital noise.
- macOS Say remains a fallback.
- Piper is treated as a legacy option and is only shown when already installed.

## macOS installation

Kokoro 0.9.4 requires Python 3.10, 3.11, or 3.12. The setup script selects a compatible installation and can install Homebrew Python 3.12 when necessary.

```bash
cd ~/Downloads/free_documentary_generator_v4
chmod +x setup.sh run.sh
./setup.sh
./run.sh
```

The setup installs:

- Kokoro 0.9.4
- its English pronunciation package
- NumPy and SoundFile
- `espeak-ng` through Homebrew when available

The first voice preview downloads the Kokoro model and selected voice into the normal Hugging Face cache. Later runs reuse the local cache.

For caption burn-in on macOS:

```bash
brew install ffmpeg-full
```

## Recommended narrator settings

- Engine: `Kokoro Local (recommended)`
- Voice: `Warm American female — Heart`
- Delivery speed: `0.92`
- Thought-group pause: `0.36` seconds
- Paragraph pause: `0.72` seconds

Use **Preview narrator** before building. Different voices suit different topics, and apparently documentaries are not improved by choosing a narrator solely because its identifier looks impressive.

## Starting the application

```bash
./run.sh
```

Then open the Streamlit address shown in Terminal, normally:

```text
http://localhost:8501
```

## Visual workflow

Before a full build:

1. Test Wikimedia media.
2. Test Pexels media when using a Pexels key.
3. Preview the narrator.
4. Build a one-minute 720p test.
5. Review `media_search_report.txt`, `credits.txt`, and the output video.

## Important files

```text
documentary_generator/tts.py       Kokoro, macOS Say, pacing, normalization, validation
app.py                             Voice controls and preview interface
documentary_generator/pipeline.py Narrator settings passed into each scene
setup.sh                           Compatible Python and Kokoro installation
requirements.txt                   Reproducible Python dependencies
```

## Troubleshooting

### Kokoro cannot be installed

Check the Python version:

```bash
python3 --version
```

Kokoro 0.9.4 requires Python below 3.13. Running `./setup.sh` will select or install Python 3.12 on a Homebrew-based Mac.

### `espeak-ng` is missing

```bash
brew install espeak-ng
```

### The first preview appears slow

The model is being downloaded and initialized. Subsequent previews use the cache.

### Narration still sounds too fast

Lower delivery speed to `0.88` or increase the thought-group pause to around `0.42` seconds. Do not push every pause to one second unless the intended style is “narrator has forgotten the next sentence.”

### No visual media is found

Use the media test buttons first. The full diagnostic trail is written to the output project’s `media_search_report.txt`.
