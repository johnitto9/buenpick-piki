from uuid import uuid4

import pytest

from piki.db.handoffs import HandoffRequest


def test_handoff_request_rejects_empty_operational_fields() -> None:
    values = {
        "conversation_id": uuid4(),
        "idempotency_key": "inbound:wamid.fixture",
        "reason": "La persona pidió atención humana.",
        "trace_id": "trace-handoff-fixture",
    }

    assert HandoffRequest(**values).reason == values["reason"]
    for field in ("idempotency_key", "reason", "trace_id"):
        invalid = values | {field: ""}
        with pytest.raises(ValueError):
            HandoffRequest(**invalid)
