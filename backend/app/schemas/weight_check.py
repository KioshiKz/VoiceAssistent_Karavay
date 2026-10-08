from typing import Literal

from pydantic import BaseModel, Field, model_validator


class WeightCheckSettings(BaseModel):
    tolerance_unit: Literal["g", "percent"] = "g"
    tolerance_below: float = Field(default=0, ge=0, allow_inf_nan=False)
    tolerance_above: float = Field(default=0, ge=0, allow_inf_nan=False)
    duration_seconds: int = Field(default=5, ge=1, le=86400)
    enforce_minimum_weight: bool = True

    @model_validator(mode="before")
    @classmethod
    def legacy_tolerance(cls, values):
        if isinstance(values, dict) and "tolerance_g" in values:
            values = dict(values)
            values.setdefault("tolerance_below", values["tolerance_g"])
            values.setdefault("tolerance_above", values["tolerance_g"])
        return values


def merge_weight_params(defaults: dict | None, overrides: dict | None) -> dict:
    result = {**(defaults or {}), **(overrides or {})}
    # An explicit legacy gram tolerance still overrides template defaults.
    if overrides and "tolerance_g" in overrides:
        if "tolerance_below" not in overrides and "tolerance_above" not in overrides:
            result.pop("tolerance_below", None)
            result.pop("tolerance_above", None)
            result["tolerance_unit"] = "g"
    return result
