import time
from enum import StrEnum
from typing import Protocol

from pydantic import Field

from piki.core.logging import get_logger
from piki.domain.contracts import ContractModel


class LifecycleEvent(StrEnum):
    MESSAGE_RECEIVED = "message_received"
    INTENT_RESOLVED = "intent_resolved"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    CONTEXT_BUILT = "context_built"
    TEMPLATE_RENDERED = "template_rendered"
    LLM_STARTED = "llm_started"
    LLM_FINISHED = "llm_finished"
    GROUNDING_CHECKED = "grounding_checked"
    DELIVERY_ATTEMPTED = "delivery_attempted"
    DELIVERY_SUCCEEDED = "delivery_succeeded"
    DELIVERY_FAILED = "delivery_failed"


class EventOutcome(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class LifecycleRecord(ContractModel):
    event: LifecycleEvent
    trace_id: str = Field(min_length=1, max_length=128)
    component: str = Field(min_length=1, max_length=100)
    outcome: EventOutcome
    duration_ms: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=100)
    confirmed_count: int | None = Field(default=None, ge=0)
    unavailable_count: int | None = Field(default=None, ge=0)


class EventSink(Protocol):
    def emit(self, record: LifecycleRecord) -> None: ...


class NullEventSink:
    def emit(self, record: LifecycleRecord) -> None:
        return None


class StructlogEventSink:
    def emit(self, record: LifecycleRecord) -> None:
        values = record.model_dump(mode="json", exclude={"event"}, exclude_none=True)
        get_logger().info(record.event.value, **values)


class RecordingEventSink:
    def __init__(self) -> None:
        self.records: list[LifecycleRecord] = []

    def emit(self, record: LifecycleRecord) -> None:
        self.records.append(record)


class LifecycleObserver:
    def __init__(self, sink: EventSink | None = None) -> None:
        self._sink = sink or NullEventSink()

    @staticmethod
    def started_at() -> float:
        return time.perf_counter()

    def emit(
        self,
        event: LifecycleEvent,
        *,
        trace_id: str,
        component: str,
        outcome: EventOutcome,
        started_at: float | None = None,
        error_code: str | None = None,
        confirmed_count: int | None = None,
        unavailable_count: int | None = None,
    ) -> None:
        duration_ms = 0
        if started_at is not None:
            duration_ms = max(0, int((time.perf_counter() - started_at) * 1000))
        self._sink.emit(
            LifecycleRecord(
                event=event,
                trace_id=trace_id,
                component=component,
                outcome=outcome,
                duration_ms=duration_ms,
                error_code=error_code,
                confirmed_count=confirmed_count,
                unavailable_count=unavailable_count,
            )
        )
