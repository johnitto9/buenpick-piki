from piki.domain.contracts import ResponseMode
from piki.prompts.policies import PolicyName
from tests.golden.support import GoldenConversationHarness


async def test_greeting_is_piki_without_commercial_tools_or_internal_language() -> None:
    query = "Hola Piki"
    expected = (
        "¡Hola! Soy Piki, el asistente de BuenPick. "
        "Te ayudo a descubrir alimentos para rescatar. ¿Qué estás buscando?"
    )

    run = await GoldenConversationHarness().run(
        policy_name=PolicyName.EXPLAIN_BUENPICK,
        query=query,
        scripted_response=expected,
        trace_id="golden-greeting",
    )

    assert run.outcome.text == expected
    assert run.outcome.mode is ResponseMode.NON_COMMERCIAL_LLM
    assert run.outcome.used_fallback is False
    assert run.outcome.trace_id == "golden-greeting"
    assert run.policy.allowed_tools == ()
    assert len(run.requests) == 1
    assert run.requests[0].conversation[0].text == query
    assert '"Hola Piki"' in run.requests[0].evidence_prompt
    assert "Sos Piki" in run.requests[0].system_prompt

    final_text = run.outcome.text.casefold()
    assert "piki" in final_text
    assert "buenpick" in final_text
    assert "rescat" in final_text
    for forbidden in (
        "delify",
        "system prompt",
        "tool_result",
        "datos confirmados",
        "trace_id",
    ):
        assert forbidden not in final_text
