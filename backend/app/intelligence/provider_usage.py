"""Organization budgets and durable dispatch fencing, shared by chat and worker jobs."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import now
from app.intelligence.providers import ProviderUnavailable
from app.models import Conversation, Document, Membership, Message, Organization, ProviderRequest

scope = ContextVar("provider_scope", default=None)


@contextmanager
def provider_scope(engine, org, user, key, documents):
    token = scope.set((engine, org, user, key, [str(d) for d in documents]))
    try:
        yield
    finally:
        scope.reset(token)


def reserve(settings, fingerprint, input_bound):
    context = scope.get()
    if context is None:
        raise ProviderUnavailable("Provider request requires authorized accounting context")
    engine, org, user, key, documents = context
    factor = settings.llm_max_retries + 1
    tokens = (input_bound + settings.llm_max_output_tokens) * factor
    cost = (
        factor
        * (
            input_bound * settings.llm_input_usd_per_million
            + settings.llm_max_output_tokens * settings.llm_output_usd_per_million
        )
        / 1_000_000
    )
    with Session(engine) as db:
        db.scalar(select(Organization).where(Organization.id == org).with_for_update())
        if not db.scalar(
            select(Membership.id).where(
                Membership.organization_id == org,
                Membership.user_id == user,
            )
        ):
            raise ProviderUnavailable("Organization membership is no longer available")
        live = db.scalars(
            select(Document)
            .where(
                Document.organization_id == org,
                Document.id.in_(documents),
                Document.deleted_at.is_(None),
                Document.status == "completed",
            )
            .order_by(Document.id)
            .with_for_update()
        ).all()
        if len(live) != len(set(documents)):
            raise ProviderUnavailable("Provider source documents changed or were deleted")
        if key.startswith("message:"):
            conversation = db.scalar(
                select(Conversation)
                .join(
                    Message,
                    Message.conversation_id == Conversation.id,
                )
                .where(
                    Message.id == key.removeprefix("message:"),
                    Conversation.organization_id == org,
                    Conversation.user_id == user,
                )
                .with_for_update(of=Conversation)
            )
            if conversation is None:
                raise ProviderUnavailable("Conversation is no longer available")
        previous = db.scalar(select(ProviderRequest).where(ProviderRequest.operation_key == key))
        if previous:
            if previous.organization_id != org or previous.fingerprint != fingerprint:
                raise ProviderUnavailable(
                    "Provider request changed; explicitly start a new analysis"
                )
            if previous.state == "received" and previous.response is not None:
                return previous.id, previous.response
            raise ProviderUnavailable(
                "Previous provider outcome is unavailable or uncertain; explicit retry required"
            )
        start = now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Keep conservative reservations even when usage is unavailable; no silent refunds.
        total_tokens, total_cost, requests = db.execute(
            select(
                func.coalesce(func.sum(ProviderRequest.reserved_tokens), 0),
                func.coalesce(func.sum(ProviderRequest.reserved_cost), 0),
                func.count(),
            ).where(
                ProviderRequest.organization_id == org,
                ProviderRequest.created_at >= start,
                ProviderRequest.created_at < start + timedelta(days=1),
            )
        ).one()
        if (
            total_tokens + tokens > settings.llm_daily_tokens
            or float(total_cost) + cost > settings.llm_daily_cost_usd
            or requests >= settings.ai_daily_requests
        ):
            raise ProviderUnavailable("Organization AI request/token/cost budget reached")
        row = ProviderRequest(
            operation_key=key,
            organization_id=org,
            user_id=user,
            model=settings.llm_model,
            fingerprint=fingerprint,
            document_ids=documents,
            reserved_tokens=tokens,
            reserved_cost=cost,
            attempts=0,
        )
        db.add(row)
        db.flush()
        identity = row.id
        db.commit()
        return identity, None


def record(identity, settings, *, state, response=None, usage=None, attempt=None):
    engine, org, _, _, _ = scope.get()
    with Session(engine) as db:
        # Deletion locks and redacts this same row, fencing late cache writes.
        row = db.get(ProviderRequest, identity, with_for_update=True)
        if row.state == "redacted":
            raise ProviderUnavailable("Source document was deleted during generation")
        row.state = state
        if attempt is not None:
            row.attempts = attempt
        row.response = response
        if usage:
            a, b = usage.get("input_tokens"), usage.get("output_tokens")
            if type(a) is int and type(b) is int and a >= 0 and b >= 0:
                row.input_tokens, row.output_tokens = a, b
                row.estimated_cost = (
                    a * settings.llm_input_usd_per_million + b * settings.llm_output_usd_per_million
                ) / 1_000_000
        db.commit()


def usage_for(db, org, key):
    row = db.scalar(
        select(ProviderRequest).where(
            ProviderRequest.operation_key == key, ProviderRequest.organization_id == org
        )
    )
    if row is None:
        return None
    return {
        "model": row.model,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "estimated_cost_usd": row.estimated_cost,
        "reserved_cost_usd": row.reserved_cost,
        "attempts": row.attempts,
        "state": row.state,
    }
