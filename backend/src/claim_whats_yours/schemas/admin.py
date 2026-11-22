"""Request bodies for admin scheme endpoints. Unknown keys are rejected."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ReviewerBody(BaseModel):
    """Body for recording a human verification."""

    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1, max_length=120)
    verified_at: date


class ActorBody(BaseModel):
    """Body naming the person who performs a publish or archive step."""

    model_config = ConfigDict(extra="forbid")

    actor: str = Field(min_length=1, max_length=120)
