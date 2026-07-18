from piki.domain.contracts import ToolResult
from piki.evidence.buenpick import search_result_evidence
from piki.integrations.buenpick.models import PickSearchResponse, PickSummary
from piki.prompts.policies import PolicyName
from tests.golden.support import GoldenConversationHarness


def search_result(*items: PickSummary, trace_id: str) -> ToolResult[PickSearchResponse]:
    return ToolResult[PickSearchResponse](
        success=True,
        data=PickSearchResponse(items=items, total=len(items)),
        latency_ms=7,
        trace_id=trace_id,
    )


async def test_search_results_use_current_buenpick_evidence_and_ars_cents() -> None:
    trace_id = "golden-search-results"
    tool_result = search_result(
        PickSummary.model_validate(
            {
                "id": "pick-golden-1",
                "title": "Bolsa sorpresa de panadería",
                "description": "Selección de alimentos rescatables del día.",
                "price": 250000,
                "original_price": 600000,
                "available_quantity": 2,
                "status": "AVAILABLE",
                "image_url": "https://cdn.buenpick.invalid/pick-golden-1.jpg",
                "commerce": {
                    "id": "commerce-golden-1",
                    "name": "Comercio Barrio",
                },
            }
        ),
        trace_id=trace_id,
    )
    evidence = search_result_evidence(tool_result)
    expected = (
        "Encontré una opción disponible para rescatar: Bolsa sorpresa de panadería "
        "de Comercio Barrio, a $2.500,00. Quedan 2. ¿Querés ver el detalle?"
    )

    run = await GoldenConversationHarness().run(
        policy_name=PolicyName.DISCOVER_PICKS,
        query="¿Hay algo de panadería para rescatar?",
        scripted_response=expected,
        trace_id=trace_id,
        confirmed_data=evidence.confirmed_data,
        actions_performed=evidence.actions_performed,
    )

    assert run.outcome.text == expected
    assert run.outcome.used_fallback is False
    assert run.outcome.trace_id == tool_result.trace_id
    assert len(run.requests) == 1
    assert "$2.500,00" in run.requests[0].evidence_prompt
    assert "Available quantity: 2" in run.requests[0].evidence_prompt
    assert "Comercio Barrio" in run.requests[0].evidence_prompt
    assert "pick-golden-1" not in run.outcome.text
    assert "600000" not in run.outcome.text


async def test_empty_search_is_confirmed_absence_not_an_error() -> None:
    trace_id = "golden-search-empty"
    tool_result = search_result(trace_id=trace_id)
    evidence = search_result_evidence(tool_result)
    expected = (
        "No encontré picks disponibles para esa búsqueda ahora. "
        "Probemos con otro alimento o zona."
    )

    run = await GoldenConversationHarness().run(
        policy_name=PolicyName.DISCOVER_PICKS,
        query="¿Hay sushi para rescatar?",
        scripted_response=expected,
        trace_id=trace_id,
        confirmed_data=evidence.confirmed_data,
        actions_performed=evidence.actions_performed,
    )

    assert tool_result.success is True
    assert tool_result.data is not None
    assert tool_result.data.total == 0
    assert evidence.unavailable_data == ()
    assert evidence.actions_performed[0].outcome == "succeeded"
    assert "returned no available picks" in run.requests[0].evidence_prompt
    assert run.outcome.text == expected
    assert run.outcome.used_fallback is False
    assert "error" not in run.outcome.text.casefold()
