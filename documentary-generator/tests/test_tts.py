from documentary_generator.tts import KOKORO_VOICES, narration_groups


def test_kokoro_default_voice_exists() -> None:
    assert KOKORO_VOICES["Warm American female — Heart"] == "af_heart"


def test_narration_groups_preserve_paragraph_ends() -> None:
    text = (
        "Artificial intelligence did not arrive in a single moment. "
        "It developed through decades of experiments, failures, and modest breakthroughs. "
        "Each generation inherited tools from the one before it.\n\n"
        "Then the pace changed. Larger datasets and faster computers made old ideas practical."
    )
    groups = narration_groups(text)
    assert groups
    assert sum(1 for _, paragraph_end in groups if paragraph_end) == 2
    assert "Artificial intelligence" in groups[0][0]


def test_short_sentences_are_bundled() -> None:
    text = "The room was quiet. The machine was not. It clicked. It waited. Then it answered."
    groups = narration_groups(text)
    assert len(groups) == 1
