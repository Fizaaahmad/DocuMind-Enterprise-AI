"""Provider-neutral structured response contracts; references remain untrusted until checked."""

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Reference(Strict):
    source_id: str
    quote: str = Field(min_length=1, max_length=10000)


class Claim(Strict):
    text: str = Field(min_length=1, max_length=4000)
    evidence: list[Reference] = Field(min_length=1, max_length=8)


class Answer(Strict):
    claims: list[Claim] = Field(max_length=20)


class ExtractedField(Strict):
    name: str
    raw: str
    normalized: str | None
    evidence: list[Reference] = Field(min_length=1, max_length=8)


class Finding(Strict):
    name: str
    severity: str
    rationale: str
    evidence: list[Reference] = Field(min_length=1, max_length=8)


class Obligation(Strict):
    action: str
    responsible_party: str | None
    deadline: str | None
    conditions: str | None
    uncertainty: str | None
    evidence: list[Reference] = Field(min_length=1, max_length=8)


class Explanation(Strict):
    change_index: int
    explanation: str
    evidence: list[Reference] = Field(min_length=1, max_length=8)


class Analysis(Strict):
    fields: list[ExtractedField] = Field(max_length=100)
    risks: list[Finding] = Field(max_length=100)
    obligations: list[Obligation] = Field(max_length=100)
    explanations: list[Explanation] = Field(max_length=100)
