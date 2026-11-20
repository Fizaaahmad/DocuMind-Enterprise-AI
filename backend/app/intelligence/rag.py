"""Grounding contract enforced without provider-specific citation features."""

import re
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
    except ProviderUnavailable:
        raise
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
        numbers = []
        quotes = []
        for source_id, quote in [(claim.source_id, claim.quote), *claim.additional]:
            source = by_id.get(source_id)
            if not source or not quote.strip() or quote not in source["text"]:
                raise ProviderUnavailable("Unsupported answer evidence; no answer published")
            offset = source["start_offset"] + source["text"].index(quote)
            citations.append(
                {k: v for k, v in source.items() if k != "text"}
                | {
                    "quote": quote,
                    "start_offset": offset,
                    "end_offset": offset + len(quote),
                }
            )
            numbers.append(str(len(citations)))
            quotes.append(quote)
        prose = claim.text if claim.text is not None else claim.quote
        if claim.text is not None:
            validate_facts(prose, "\n".join(quotes))
        paragraphs.append(f"{prose} [{', '.join(numbers)}]")
    if sum(map(len, paragraphs)) > settings.llm_max_output_tokens * 8:
        raise ProviderUnavailable("Provider response exceeded the output budget")
    return "\n\n".join(paragraphs) or ABSTENTION, citations


def validate_facts(text, quotes):
    """Conservative consistency safeguard, not a proof of semantic entailment."""

    def amounts(value):
        return {v.replace(",", "") for v in re.findall(r"(?<!\w)\d+(?:[,.]\d+)*(?:%)?", value)}

    if not amounts(text).issubset(amounts(quotes)):
        raise ProviderUnavailable(
            "Generated claim contains unsupported numbers; no result published"
        )
    if re.search(r"\[[^\]]*\]|https?://", text):
        raise ProviderUnavailable("Provider-supplied citations or URLs are not accepted")
