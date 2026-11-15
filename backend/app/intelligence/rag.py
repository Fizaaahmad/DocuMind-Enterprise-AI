"""Grounding contract enforced without provider-specific citation features."""

import time

from app.intelligence.providers import (
    Evidence,
    ProviderResult,
    ProviderUnavailable,
    SupportedClaim,
    generation_settings,
)

ABSTENTION = (
    "Insufficient document evidence to answer. Try another question or index more documents."
)


def answer(provider, settings, question, history, sources):
    if not sources:
        return ABSTENTION, []
    started = time.monotonic()
    try:
        result = provider.generate(
            question,
            history,
            [Evidence(s["source_id"], s["text"]) for s in sources],
            generation_settings(settings),
        )
    except TimeoutError:
        raise ProviderUnavailable("The answer provider timed out; please try again") from None
    except Exception:
        raise ProviderUnavailable("The answer provider failed; please try again") from None
    if time.monotonic() - started > settings.llm_timeout_seconds:
        raise ProviderUnavailable("The answer provider exceeded its time limit")
    by_id = {s["source_id"]: s for s in sources}
    citations, paragraphs = [], []
    if not isinstance(result, ProviderResult) or not isinstance(result.claims, list):
        raise ProviderUnavailable("Provider returned an invalid response")
    if len(result.claims) > 20:
        raise ProviderUnavailable("Provider returned too many claims")
    for claim in result.claims:
        if (
            not isinstance(claim, SupportedClaim)
            or not isinstance(claim.source_id, str)
            or not isinstance(claim.quote, str)
        ):
            raise ProviderUnavailable("Provider returned an invalid claim")
        source = by_id.get(claim.source_id)
        if not source or not claim.quote.strip() or claim.quote not in source["text"]:
            raise ProviderUnavailable(
                "Provider returned unsupported evidence; no answer was published"
            )
        # No free-form provider prose is published: exact passages establish support.
        quote = claim.quote
        offset = source["start_offset"] + source["text"].index(quote)
        citations.append(
            {k: v for k, v in source.items() if k != "text"}
            | {
                "quote": quote,
                "start_offset": offset,
                "end_offset": offset + len(quote),
            }
        )
        paragraphs.append(f"{quote} [{len(citations)}]")
    if sum(map(len, paragraphs)) > settings.llm_max_output_tokens * 8:
        raise ProviderUnavailable("Provider response exceeded the output budget")
    return "\n\n".join(paragraphs) or ABSTENTION, citations
