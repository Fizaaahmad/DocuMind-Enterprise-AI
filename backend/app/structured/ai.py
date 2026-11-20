"""AI candidates reuse immutable sources and the existing item/review lifecycle."""

from app.intelligence.providers import ProviderUnavailable, get_provider
from app.intelligence.rag import validate_facts
from app.structured.engine import compare, make, normalize
from app.structured.sources import evidence


def analyze_ai(left, right, definition, mode, settings):
    provider = get_provider(settings)
    if settings.llm_provider != "openai" or not hasattr(provider, "analyze"):
        raise ProviderUnavailable("OpenAI structured analysis is unavailable")
    sections = {str(s.id): s for s in left + right}
    changes = compare(left, right) if mode == "compare" else []
    response = provider.analyze(
        {
            "mode": mode,
            "template": definition,
            "sources": [
                {"id": str(s.id), "side": "before" if s in left else "after", "text": s.text}
                for s in sections.values()
            ],
            "actual_changes": [
                {
                    "index": i,
                    "before": r["original"]["before"],
                    "after": r["original"]["after"],
                    "evidence": r["evidence"],
                }
                for i, r in enumerate(changes)
            ],
            "task": "Extract semantic fields, grounded risk candidates and explicit obligations. "
            "For compare return only explanations of actual_changes; other arrays empty. "
            "For extract return explanations empty. normalized is optional display text only.",
        }
    )

    def references(items):
        result = []
        for item in items:
            section = sections.get(item.source_id)
            if not section or not item.quote.strip() or item.quote not in section.text:
                raise ProviderUnavailable("AI evidence does not match an authorized source")
            start = section.text.index(item.quote)
            result.append(evidence(section, start, start + len(item.quote)))
        return result

    if mode == "compare":
        if response.fields or response.risks or response.obligations:
            raise ProviderUnavailable("AI comparison returned unrelated findings")
        seen = set()
        for explanation in response.explanations:
            index = explanation.change_index
            if not 0 <= index < len(changes) or index in seen:
                raise ProviderUnavailable("AI comparison referenced an invalid change")
            seen.add(index)
            refs = references(explanation.evidence)
            actual = changes[index]["evidence"]
            for ref in refs:
                if not any(
                    ref["section_id"] == a["section_id"]
                    and a["start"] <= ref["start"] < ref["end"] <= a["end"]
                    for a in actual
                ):
                    raise ProviderUnavailable("AI explanation does not cite the actual text change")
            validate_facts(explanation.explanation, "\n".join(r["quote"] for r in refs))
            changes[index]["original"].update(
                {
                    "ai_explanation": explanation.explanation,
                    "provenance": "openai",
                    "review_required": True,
                }
            )
        return changes
    if response.explanations:
        raise ProviderUnavailable("Extraction returned unrelated comparison explanations")
    results = []
    fields = {f["name"]: f for f in definition.get("fields", [])}
    candidates = {}
    for candidate in response.fields:
        field = fields.get(candidate.name)
        if field is None:
            raise ProviderUnavailable("AI returned an unknown template field")
        refs = references(candidate.evidence)
        if not candidate.raw.strip() or not any(candidate.raw in ref["quote"] for ref in refs):
            raise ProviderUnavailable("AI field raw value is unsupported by its evidence")
        candidates.setdefault(candidate.name, []).append((candidate, refs))
    for name, field in fields.items():
        found = candidates.get(name, [])
        if not found:
            results.append(
                make(
                    "field",
                    name,
                    {
                        "raw": None,
                        "value": None,
                        "type": field["type"],
                        "required": field["required"],
                        "provenance": "openai",
                        "note": "Not established by AI; not proof of absence",
                    },
                    [],
                    "missing_required" if field["required"] else "not_found",
                )
            )
            continue
        candidate, refs = found[0]
        value, validation = normalize(candidate.raw, field["type"])
        # Backend normalization is authoritative, including dates/currencies. Preserve suggestions
        # without accepting a model-created deadline or monetary interpretation as validated.
        results.append(
            make(
                "field",
                name,
                {
                    "raw": candidate.raw,
                    "value": value,
                    "type": field["type"],
                    "required": field["required"],
                    "candidates": [c.raw for c, _ in found],
                    "provenance": "openai",
                    "review_required": True,
                },
                [r for _, rr in found for r in rr],
                "ambiguous" if len({c.raw for c, _ in found}) > 1 else validation,
            )
        )
    # Configured rules evaluate the AI-extracted, backend-normalized fields through existing logic.
    # Feed no synthetic document text: the rule evaluator accepts authorized extracted items.
    from app.structured.engine import evaluate_rules

    results.extend(evaluate_rules(left, definition, results))
    for risk in response.risks:
        refs = references(risk.evidence)
        if risk.severity not in {"low", "medium", "high"}:
            raise ProviderUnavailable("AI returned an invalid severity")
        validate_facts(risk.name + " " + risk.rationale, "\n".join(r["quote"] for r in refs))
        results.append(
            make(
                "risk",
                risk.name,
                {
                    "severity": risk.severity,
                    "note": risk.rationale,
                    "provenance": "openai",
                    "review_required": True,
                    "disclaimer": "AI review candidate; not a legal conclusion",
                },
                refs,
                "candidate",
            )
        )
    if definition.get("obligations"):
        for obligation in response.obligations:
            refs = references(obligation.evidence)
            text = "\n".join(r["quote"] for r in refs)
            # Commitments/parties/dates must be extractive; uncertainty remains explicit.
            if obligation.action not in text or not obligation.action.strip():
                raise ProviderUnavailable("AI obligation action is unsupported")
            if obligation.responsible_party and obligation.responsible_party not in text:
                raise ProviderUnavailable("AI obligation party is unsupported")
            if obligation.conditions and obligation.conditions not in text:
                raise ProviderUnavailable("AI obligation conditions are unsupported")
            deadline = None
            if obligation.deadline:
                deadline, valid = normalize(obligation.deadline, "date")
                if valid != "valid" or obligation.deadline not in text:
                    raise ProviderUnavailable(
                        "AI obligation deadline requires an exact ISO source date"
                    )
            results.append(
                make(
                    "obligation",
                    "AI commitment candidate",
                    {
                        "commitment": obligation.action,
                        "responsible_party": obligation.responsible_party,
                        "deadline": deadline,
                        "conditions": obligation.conditions,
                        "note": obligation.uncertainty
                        or "Confirm party, conditions and deadline before reliance",
                        "provenance": "openai",
                        "review_required": True,
                    },
                    refs,
                    "candidate",
                )
            )
    return results
