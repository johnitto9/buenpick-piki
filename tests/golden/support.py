from dataclasses import dataclass

from piki.composition.contracts import (
    CompositionRequest,
    CompositionResult,
    ConversationTurn,
)
from piki.composition.engine import ResponseEngine, ResponseOutcome
from piki.composition.service import ResponseComposer
from piki.domain.contracts import EvidenceItem, PerformedAction, ResponseMode
from piki.prompts.policies import PolicyDefinition, PolicyName, get_policy


class ScriptedLLM:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.requests: list[CompositionRequest] = []

    async def compose(self, request: CompositionRequest) -> CompositionResult:
        self.requests.append(request)
        return CompositionResult(
            text=self._response_text,
            provider_response_id=f"golden:{request.trace_id}",
            model="golden-scripted-model",
            trace_id=request.trace_id,
        )


@dataclass(frozen=True)
class GoldenRun:
    policy: PolicyDefinition
    outcome: ResponseOutcome
    requests: tuple[CompositionRequest, ...]


class GoldenConversationHarness:
    async def run(
        self,
        *,
        policy_name: PolicyName,
        query: str,
        scripted_response: str,
        trace_id: str,
        confirmed_data: tuple[EvidenceItem, ...] = (),
        unavailable_data: tuple[str, ...] = (),
        actions_performed: tuple[PerformedAction, ...] = (),
        active_pick_id: str | None = None,
    ) -> GoldenRun:
        policy = get_policy(policy_name)
        packet = policy.context_packet(
            query=query,
            trace_id=trace_id,
            confirmed_data=confirmed_data,
            unavailable_data=unavailable_data,
            actions_performed=actions_performed,
            active_pick_id=active_pick_id,
        )
        adapter = ScriptedLLM(scripted_response)
        engine = ResponseEngine(ResponseComposer(adapter))
        outcome = await engine.respond(
            packet,
            conversation=(ConversationTurn(role="user", text=query),),
            deterministic_text=(
                scripted_response
                if policy.response_mode is ResponseMode.DETERMINISTIC
                else None
            ),
        )
        return GoldenRun(
            policy=policy,
            outcome=outcome,
            requests=tuple(adapter.requests),
        )
