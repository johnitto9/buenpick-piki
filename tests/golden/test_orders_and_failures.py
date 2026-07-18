import pytest

from piki.domain.contracts import ToolErrorCode, ToolResult
from piki.evidence.buenpick import order_result_evidence, search_result_evidence
from piki.integrations.buenpick.models import CustomerOrder, PickSearchResponse
from piki.prompts.policies import PolicyName, get_policy
from tests.golden.support import GoldenConversationHarness


def customer_order() -> CustomerOrder:
    return CustomerOrder.model_validate(
        {
            "id": "order-golden-owned",
            "status": "ready",
            "commerce": {
                "id": "commerce-order-golden",
                "name": "Mercado Circular",
                "address": "Dirección comercial de fixture",
                "opening_hours": None,
            },
            "picks": [
                {
                    "pick_id": "pick-order-golden",
                    "title": "Rescate del día",
                    "quantity": 2,
                    "unit_price": 150000,
                    "line_total": 300000,
                    "image_url": None,
                }
            ],
            "total": 300000,
            "fulfillment": {
                "type": "pickup",
                "delivery_address": None,
                "delivery_notes": None,
                "pickup_code": "BP-4821",
            },
            "pickup": {
                "instructions": "Presentá el código al retirar.",
                "store_address": "Dirección comercial de fixture",
            },
            "dates": {
                "created_at": "2026-07-16T15:00:00Z",
                "expires_at": None,
                "confirmed_at": "2026-07-16T15:05:00Z",
                "paid_at": "2026-07-16T15:06:00Z",
                "preparing_at": "2026-07-16T16:00:00Z",
                "ready_at": "2026-07-16T17:00:00Z",
                "out_for_delivery_at": None,
                "delivered_at": None,
                "picked_up_at": None,
            },
        }
    )


async def test_owned_order_uses_only_confirmed_non_ownership_evidence() -> None:
    trace_id = "golden-owned-order"
    tool_result = ToolResult[CustomerOrder](
        success=True,
        data=customer_order(),
        latency_ms=8,
        trace_id=trace_id,
    )
    evidence = order_result_evidence(tool_result)
    expected = (
        "Tu orden está lista para retirar en Mercado Circular. "
        "El total es $3.000,00 y tu código de retiro es BP-4821."
    )

    run = await GoldenConversationHarness().run(
        policy_name=PolicyName.ORDER_STATUS,
        query="¿Cómo está mi orden?",
        scripted_response=expected,
        trace_id=trace_id,
        confirmed_data=evidence.confirmed_data,
        actions_performed=evidence.actions_performed,
    )

    assert run.outcome.text == expected
    assert run.outcome.used_fallback is False
    assert "order-golden-owned" not in run.outcome.text
    assert "delivery_address" not in run.requests[0].evidence_prompt
    assert "customer_phone" not in run.requests[0].evidence_prompt
    assert "$3.000,00" in run.requests[0].evidence_prompt
    assert "BP-4821" in run.requests[0].evidence_prompt


def test_foreign_order_is_non_enumerating_and_never_builds_commercial_packet() -> None:
    tool_result = ToolResult[CustomerOrder](
        success=False,
        error_code=ToolErrorCode.UNAUTHORIZED,
        user_safe_message="No pude validar esa orden con los datos proporcionados.",
        latency_ms=5,
        trace_id="golden-foreign-order",
    )
    evidence = order_result_evidence(tool_result)

    assert evidence.confirmed_data == ()
    assert evidence.unavailable_data == (
        "No pude validar esa orden con los datos proporcionados.",
    )
    assert "existe" not in evidence.unavailable_data[0]
    assert "pertenece" not in evidence.unavailable_data[0]
    with pytest.raises(ValueError, match="requires confirmed evidence"):
        get_policy(PolicyName.ORDER_STATUS).context_packet(
            query="¿Cómo está la orden?",
            trace_id=tool_result.trace_id,
            unavailable_data=evidence.unavailable_data,
            actions_performed=evidence.actions_performed,
        )


def test_buenpick_timeout_cannot_become_a_commercial_search_answer() -> None:
    tool_result = ToolResult[PickSearchResponse](
        success=False,
        error_code=ToolErrorCode.TIMEOUT,
        user_safe_message="BuenPick tardó demasiado en responder.",
        latency_ms=5000,
        trace_id="golden-buenpick-timeout",
    )
    evidence = search_result_evidence(tool_result)

    assert evidence.confirmed_data == ()
    assert evidence.actions_performed[0].outcome == "failed"
    assert tool_result.error_code is ToolErrorCode.TIMEOUT
    with pytest.raises(ValueError, match="requires confirmed evidence"):
        get_policy(PolicyName.DISCOVER_PICKS).context_packet(
            query="¿Qué puedo rescatar?",
            trace_id=tool_result.trace_id,
            unavailable_data=evidence.unavailable_data,
            actions_performed=evidence.actions_performed,
        )
