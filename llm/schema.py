"""Input/output contract for POST /enrich, from JOB-CARD.md."""
from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    fiction = "fiction"
    nonfiction = "nonfiction"
    poetry = "poetry"
    biography = "biography"
    childrens = "childrens"
    other = "other"


class QualityFlag(str, Enum):
    thin_description = "thin_description"
    non_english = "non_english"
    promotional_tone = "promotional_tone"
    possible_mismatch = "possible_mismatch"


class EnrichRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)


class EnrichResult(BaseModel):
    category: Category
    summary: str = Field(min_length=1, max_length=200)
    quality_flags: list[QualityFlag] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


STUB_RESULT = EnrichResult(
    category=Category.fiction,
    summary="A stubbed summary returned without calling the model.",
    quality_flags=[],
    confidence=0.42,
)
