"""Bounded deterministic extraction and comparison; never claims semantic AI analysis."""

import re
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from itertools import zip_longest

from app.intelligence.providers import Evidence, generation_settings, get_provider
from app.structured.sources import evidence


def normalize(raw, kind):
    text = raw.strip()
    try:
        if kind == "text":
            return text, "valid" if text else "invalid"
        if kind == "date":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                return None, "invalid"
            return date.fromisoformat(text).isoformat(), "valid"
        if kind == "boolean" and text.lower() in {"true", "false", "yes", "no"}:
            return text.lower() in {"true", "yes"}, "valid"
        if kind == "list":
            values = [p.strip() for p in text.split(";") if p.strip()]
            return values, "valid" if values else "invalid"
        if kind == "decimal" and re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            return str(Decimal(text)), "valid"
        if kind == "money":
            found = re.fullmatch(r"([A-Z]{3})\s+(-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)", text)
            if found:
                amount = Decimal(found[2].replace(",", ""))
                return {"currency": found[1], "amount": str(amount)}, "valid"
    except (ValueError, InvalidOperation):
        pass
    return None, "invalid"


def lines(sections):
    for section in sections:
        offset = 0
        for line in section.text.splitlines(keepends=True):
            text = line.rstrip("\r\n")
            if text.strip():
                yield section, offset, text
            offset += len(line)


def make(kind, name, value, references, validation="valid"):
    return {
        "kind": kind,
        "name": name[:200],
        "original": value,
        "evidence": references,
        "validation": validation,
    }


def extract(sections, definition, settings, engine="deterministic"):
    result = []
    fields = definition.get("fields", [])
    candidates = {}
    if engine == "mock":
        provider = get_provider(settings)
        capability = getattr(provider, "extract_fields", None)
        if not provider.is_mock or capability is None:
            raise ValueError(
                "Configured provider does not support development structured extraction"
            )
        suggestions = capability(
            fields,
            [Evidence(str(s.id), s.text) for s in sections],
            generation_settings(settings),
        )
        by_id = {str(s.id): s for s in sections}
        for suggestion in suggestions:
            section = by_id.get(suggestion.source_id)
            if (
                not section
                or suggestion.quote not in section.text
                or suggestion.value not in suggestion.quote
            ):
                raise ValueError("Structured provider returned unsupported evidence")
            start = section.text.index(suggestion.quote)
            candidates.setdefault(suggestion.field, []).append(
                (suggestion.value, evidence(section, start, start + len(suggestion.quote)))
            )
    else:
        for field in fields:
            pattern = re.compile(r"^\s*" + re.escape(field["label"]) + r"\s*:\s*(.+?)\s*$", re.I)
            for section, offset, line in lines(sections):
                match = pattern.match(line)
                if match:
                    candidates.setdefault(field["name"], []).append(
                        (match[1], evidence(section, offset, offset + len(line)))
                    )
    for field in fields:
        found = candidates.get(field["name"], [])
        if len(found) > 50:
            raise ValueError("More than 50 occurrences of a field; narrow the template")
        unique = list(dict.fromkeys(raw for raw, _ in found))
        if not found:
            result.append(
                make(
                    "field",
                    field["name"],
                    {
                        "raw": None,
                        "value": None,
                        "type": field["type"],
                        "required": field["required"],
                        "note": "Not detected; coverage record identifies inspected revision",
                    },
                    [],
                    "missing_required" if field["required"] else "not_found",
                )
            )
            continue
        value, valid = normalize(unique[0], field["type"])
        result.append(
            make(
                "field",
                field["name"],
                {
                    "raw": unique[0],
                    "value": value,
                    "type": field["type"],
                    "candidates": unique,
                    "required": field["required"],
                },
                [reference for _, reference in found],
                "ambiguous" if len(unique) > 1 else valid,
            )
        )
    result.extend(evaluate_rules(sections, definition, result))
    if definition.get("obligations"):
        for section, start, text in lines(sections):
            trigger = re.search(r"\b(shall|must|agrees to|will)\b", text, re.I)
            if not trigger:
                continue
            deadline = re.search(r"\b(?:by|on)\s+(\d{4}-\d{2}-\d{2})\b", text, re.I)
            when, _ = normalize(deadline[1], "date") if deadline else (None, "not_found")
            result.append(
                make(
                    "obligation",
                    "Commitment candidate",
                    {
                        "commitment": text,
                        "responsible_party": text[: trigger.start()].strip() or None,
                        "deadline": when,
                        "note": "Literal language candidate; confirm party, scope, and deadline",
                    },
                    [evidence(section, start, start + len(text))],
                    "candidate",
                )
            )
    return result


def evaluate_rules(sections, definition, fields):
    findings = []
    for rule in definition.get("rules", []):
        related = next(
            (r for r in fields if r["kind"] == "field" and r["name"] == rule["field"]), None
        )
        refs = []
        hit = False
        note = "Configured rule matched; review candidate only"
        if rule["type"] in {"contains", "missing"}:
            for section, start, text in lines(sections):
                if rule["term"].casefold() in text.casefold():
                    refs.append(evidence(section, start, start + len(text)))
                    if len(refs) > 100:
                        raise ValueError("Rule matched more than 100 passages; narrow the rule")
            hit = bool(refs) if rule["type"] == "contains" else not refs
            if rule["type"] == "missing":
                refs = []
                note = "Term not detected across inspected revision; not proof of absence"
        elif related:
            refs = related["evidence"]
            if rule["type"] == "inconsistent":
                hit = related["validation"] == "ambiguous"
            elif related["validation"] == "valid":
                value = related["original"]["value"]
                if isinstance(value, dict):
                    value = value.get("amount")
                try:
                    hit = Decimal(str(value)) > Decimal(str(rule["threshold"]))
                except InvalidOperation:
                    hit = False
        if hit:
            findings.append(
                make(
                    "risk",
                    rule["name"],
                    {
                        "severity": rule["severity"],
                        "provenance": "configured_rule",
                        "rule": rule,
                        "note": note,
                    },
                    refs,
                    "coverage_only" if rule["type"] == "missing" else "candidate",
                )
            )
    return findings


def compare(left, right):
    a, b = list(lines(left)), list(lines(right))
    if max(len(a), len(b)) > 1500 or any(len(row[2]) > 10000 for row in a + b):
        raise ValueError(
            "Comparison exceeds 1500 paragraphs or 10000 characters per paragraph; split documents"
        )
    # Whitespace normalization is for alignment only; source quotes remain exact.
    matcher = SequenceMatcher(
        None,
        [" ".join(r[2].split()) for r in a],
        [" ".join(r[2].split()) for r in b],
        autojunk=True,
    )
    result = []
    for operation, i, j, k, end in matcher.get_opcodes():
        if operation == "equal":
            continue
        for old, new in zip_longest(a[i:j], b[k:end]):
            references = [
                evidence(s, start, start + len(text))
                for s, start, text in [r for r in [old, new] if r]
            ]
            before, after = old[2] if old else None, new[2] if new else None
            significant = bool(
                re.search(
                    r"\d|\b(shall|must|terminate|liability)\b",
                    (before or "") + " " + (after or ""),
                    re.I,
                )
            )
            result.append(
                make(
                    "change",
                    "Modified" if old and new else "Added" if new else "Removed",
                    {
                        "before": before,
                        "after": after,
                        "significance_candidate": significant,
                        "note": "Text difference; significance is a lexical review flag",
                    },
                    references,
                    "candidate",
                )
            )
    return result


def analyze(left, right, definition, mode, engine, settings):
    start = time.monotonic()
    characters = sum(len(s.text) for s in left + right)
    if characters > settings.analysis_max_characters:
        raise ValueError(
            "Analysis exceeds ANALYSIS_MAX_CHARACTERS; no partial analysis was published"
        )
    if engine == "openai":
        from app.structured.ai import analyze_ai

        result = analyze_ai(left, right, definition, mode, settings)
    else:
        result = (
            compare(left, right)
            if mode == "compare"
            else extract(left, definition, settings, engine)
        )
    if len(result) > settings.analysis_max_items:
        raise ValueError(
            "Analysis exceeds ANALYSIS_MAX_ITEMS; narrow the template or split documents"
        )
    if time.monotonic() - start > settings.analysis_timeout_seconds:
        raise ValueError(
            "Analysis exceeded ANALYSIS_TIMEOUT_SECONDS; reduce document or template size"
        )
    return result, {
        "complete": True,
        "characters": characters,
        "sections": len(left) + len(right),
        "engine_version": "openai-v1" if engine == "openai" else "deterministic-v1",
        "normalization": "backend-validated AI candidates"
        if engine == "openai"
        else ("whitespace alignment only" if mode == "compare" else "literal labels"),
    }
