import pytest

from piki.domain.contracts import (
    EvidenceItem,
    EvidenceSource,
    ResponseMode,
)
from piki.prompts.policies import (
    POLICIES,
    PolicyDefinition,
    PolicyName,
    ToolName,
    get_policy,
)


def confirmed_pick() -> EvidenceItem:
    return EvidenceItem(
        label="Pick",
        value="Pick anónimo confirmado por la API",
        source=EvidenceSource.BUENPICK_INTERNAL_API,
        source_reference="pick-test",
    )


def test_registry_covers_every_policy_exactly_once() -> None:
    assert set(POLICIES) == set(PolicyName)
    assert all(definition.name is name for name, definition in POLICIES.items())


def test_commercial_policies_require_evidence_and_never_use_free_llm() -> None:
    commercial = [policy for policy in POLICIES.values() if policy.commercial]

    assert commercial
    assert all(policy.requires_confirmed_evidence for policy in commercial)
    assert all(
        policy.response_mode is not ResponseMode.NON_COMMERCIAL_LLM
        for policy in commercial
    )
    for policy in commercial:
        with pytest.raises(ValueError):
            policy.context_packet(query="consulta", trace_id="trace-no-evidence")


def test_policy_builds_context_without_adding_commercial_facts() -> None:
    policy = get_policy(PolicyName.PICK_DETAIL)

    packet = policy.context_packet(
        query="¿Cuándo lo retiro?",
        trace_id="trace-policy",
        confirmed_data=(confirmed_pick(),),
        unavailable_data=("Contenido exacto",),
        active_pick_id="pick-test",
    )

    assert packet.task == policy.task
    assert packet.response_mode is ResponseMode.JINJA_LLM
    assert packet.writing_rules == policy.writing_rules
    assert packet.confirmed_data == (confirmed_pick(),)
    assert packet.active_pick_id == "pick-test"


def test_policy_definitions_reject_unsafe_commercial_routes() -> None:
    with pytest.raises(ValueError):
        PolicyDefinition(
            name=PolicyName.PICK_DETAIL,
            task="Ruta insegura",
            response_mode=ResponseMode.NON_COMMERCIAL_LLM,
            commercial=True,
            requires_confirmed_evidence=True,
        )
    with pytest.raises(ValueError):
        PolicyDefinition(
            name=PolicyName.PICK_DETAIL,
            task="Ruta sin evidencia",
            response_mode=ResponseMode.JINJA_LLM,
            commercial=True,
            requires_confirmed_evidence=False,
        )


def test_registry_tools_are_known_and_not_delivery_adapters() -> None:
    used_tools = {
        tool for policy in POLICIES.values() for tool in policy.allowed_tools
    }

    assert used_tools <= set(ToolName)
    assert all("send_message" not in tool.value for tool in used_tools)
    assert all("whatsapp" not in tool.value for tool in used_tools)


def test_policy_text_has_piki_domain_without_legacy_catalog_terms() -> None:
    flattened = "\n".join(
        item
        for policy in POLICIES.values()
        for item in (policy.task, *policy.writing_rules)
    )
    flattened = flattened.casefold()
    forbidden = (
        "delify",
        "delibot",
        "golosina",
        "takis",
        "doritos",
        "pocky",
        "mayorista",
        "minorista",
    )

    assert "buenpick" in flattened
    assert "rescatar alimentos" in flattened
    assert all(term not in flattened for term in forbidden)
