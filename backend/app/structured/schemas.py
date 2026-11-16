import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FieldDefinition(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")
    type: Literal["text", "date", "decimal", "money", "boolean", "list"] = "text"
    description: str = Field(default="", max_length=500)
    required: bool = False
    label: str = Field(min_length=1, max_length=100)


class RuleDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: Literal["contains", "missing", "threshold", "inconsistent"]
    term: str = Field(default="", max_length=100)
    field: str = Field(default="", max_length=50)
    threshold: float | None = Field(default=None, allow_inf_nan=False)
    severity: Literal["low", "medium", "high"] = "medium"

    @model_validator(mode="after")
    def coherent(self):
        if self.type in {"contains", "missing"} and not self.term.strip():
            raise ValueError("Keyword rules need a term")
        if self.type in {"threshold", "inconsistent"} and not self.field:
            raise ValueError("Value rules need a field")
        if self.type == "threshold" and self.threshold is None:
            raise ValueError("Threshold rules need a finite threshold")
        return self


class TemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: uuid.UUID | None = None
    fields: list[FieldDefinition] = Field(default_factory=list, max_length=40)
    rules: list[RuleDefinition] = Field(default_factory=list, max_length=40)
    obligations: bool = True

    @model_validator(mode="after")
    def unique_fields(self):
        names = [f.name for f in self.fields]
        if len(set(names)) != len(names):
            raise ValueError("Field names must be unique")
        if any(r.field and r.field not in names for r in self.rules):
            raise ValueError("Rule field must exist in the template")
        types = {field.name: field.type for field in self.fields}
        if any(
            rule.type == "threshold" and types.get(rule.field) not in {"money", "decimal"}
            for rule in self.rules
        ):
            raise ValueError("Threshold rules require money or decimal fields")
        return self


class RunInput(BaseModel):
    document_id: uuid.UUID
    revision_id: uuid.UUID | None = None
    other_document_id: uuid.UUID | None = None
    other_revision_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    mode: Literal["extract", "compare"] = "extract"
    engine: Literal["deterministic", "mock"] = "deterministic"


class EvidenceInput(BaseModel):
    section_id: uuid.UUID
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=10000)


class ReviewInput(BaseModel):
    version: int = Field(ge=1)
    action: Literal["approve", "reject", "correct", "obligation"]
    reason: str = Field(min_length=1, max_length=1000)
    value: str | None = Field(default=None, max_length=10000)
    evidence: EvidenceInput | None = None
    obligation_status: Literal["open", "in_progress", "completed", "dismissed"] | None = None
