"""Request schemas for the stateless eligibility evaluation endpoint."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Annotated[str, Field(max_length=100)]


class EvaluateFilters(BaseModel):
    """Optional narrowing applied to the evaluation results."""

    model_config = ConfigDict(extra="forbid")

    categories: list[Category] = Field(default=[], max_length=20)
    government_levels: list[Literal["central", "state", "ut", "district"]] = []


class EvaluateRequest(BaseModel):
    """Profile answers to evaluate. Nothing from this request is persisted."""

    model_config = ConfigDict(extra="forbid")

    answers: dict[str, Any]
    filters: EvaluateFilters = EvaluateFilters()
    locale: str = Field(default="en", max_length=10)
