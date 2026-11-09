"""Local API request protocol; all artifact references are opaque content hashes."""

from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.contracts.base import FrozenModel

ArtifactId = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Horizon = Annotated[int, Field(ge=1, le=168 * 3600, strict=True)]


class VersionedRequest(FrozenModel):
    schema_version: Literal["2.0"] = "2.0"
    layout_version: str


class MaterializeRequest(VersionedRequest):
    profile: Literal["large-normal", "large-peak", "promotion"]
    horizon_s: Horizon
    assignment_id: ArtifactId | None = None


class ForecastRequest(VersionedRequest):
    history_id: ArtifactId
    model: Literal["mean28", "hgb"] = "mean28"


class PlanRequest(VersionedRequest):
    scenario_id: ArtifactId
    forecast_id: ArtifactId
    budget_swaps: Literal[0, 2, 8]
    assignment_id: ArtifactId | None = None

    @field_validator("budget_swaps", mode="before")
    @classmethod
    def integer_budget(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("budget_swaps requires an integer literal")
        return value


class CompareRequest(VersionedRequest):
    scenario_id: ArtifactId
    plan_id: ArtifactId
    output_format: Literal["2.0", "2.1-proposal"] = "2.0"
