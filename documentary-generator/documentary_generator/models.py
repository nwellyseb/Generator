from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Scene(BaseModel):
    narration: str = Field(min_length=1)
    visual_query: str = Field(min_length=1)
    on_screen_text: str = ""

    @field_validator("narration", "visual_query", "on_screen_text", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> str:
        return str(value or "").strip()


class DocumentaryPlan(BaseModel):
    title: str = Field(min_length=1)
    youtube_description: str = ""
    scenes: list[Scene] = Field(min_length=1)

    @field_validator("title", "youtube_description", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> str:
        return str(value or "").strip()
