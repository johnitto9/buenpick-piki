from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from piki.db.conversations import (
    ConversationRepository,
    PersistedInbound,
    PersistStatus,
)
from piki.db.models import (
    Base,
    ConversationRecord,
    DeliveryAttemptRecord,
    DeliveryStatusEventRecord,
    HandoffRecord,
    MessageRecord,
)


def test_orm_metadata_matches_migrated_core_tables() -> None:
    assert set(Base.metadata.tables) == {
        "conversations",
        "messages",
        "handoffs",
        "delivery_attempts",
        "delivery_status_events",
    }
    conversation_constraints = {
        constraint.name for constraint in ConversationRecord.__table__.constraints
    }
    message_constraints = {
        constraint.name for constraint in MessageRecord.__table__.constraints
    }
    message_indexes = {index.name for index in MessageRecord.__table__.indexes}
    delivery_constraints = {
        constraint.name for constraint in DeliveryAttemptRecord.__table__.constraints
    }
    event_constraints = {
        constraint.name for constraint in DeliveryStatusEventRecord.__table__.constraints
    }
    handoff_constraints = {
        constraint.name for constraint in HandoffRecord.__table__.constraints
    }
    handoff_indexes = {index.name for index in HandoffRecord.__table__.indexes}

    assert "uq_conversation_channel_identity" in conversation_constraints
    assert "uq_messages_external_message_id" in message_constraints
    assert message_indexes == {
        "ix_messages_conversation_created",
        "ix_messages_processing_available",
        "ix_messages_trace_id",
    }
    assert "uq_delivery_attempts_idempotency_key" in delivery_constraints
    assert "uq_delivery_status_provider_state" in event_constraints
    assert "uq_handoffs_conversation_idempotency" in handoff_constraints
    assert handoff_indexes == {
        "ix_handoffs_status_created",
        "uq_handoffs_one_open_per_conversation",
    }


def test_persisted_inbound_contract_distinguishes_created_and_duplicate() -> None:
    conversation_id = uuid4()
    message_id = uuid4()

    created = PersistedInbound(
        status=PersistStatus.CREATED,
        conversation_id=conversation_id,
        message_id=message_id,
    )
    duplicate = PersistedInbound(
        status=PersistStatus.DUPLICATE,
        conversation_id=conversation_id,
    )

    assert created.message_id == message_id
    assert duplicate.message_id is None
    with pytest.raises(ValueError):
        PersistedInbound(
            status=PersistStatus.DUPLICATE,
            conversation_id=conversation_id,
            message_id=message_id,
        )


@pytest.mark.asyncio
async def test_history_limit_is_validated_before_database_access() -> None:
    repository = ConversationRepository(cast(AsyncSession, object()))

    with pytest.raises(ValueError):
        await repository.recent_messages(uuid4(), limit=0)
    with pytest.raises(ValueError):
        await repository.recent_messages(uuid4(), limit=101)
