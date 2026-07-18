from piki.domain.contracts import (
    ContractModel,
    EvidenceItem,
    EvidenceSource,
    PerformedAction,
    ToolResult,
)
from piki.integrations.buenpick.models import (
    CustomerOrder,
    PickSearchResponse,
    format_ars_cents,
)


class ToolEvidenceBundle(ContractModel):
    confirmed_data: tuple[EvidenceItem, ...] = ()
    unavailable_data: tuple[str, ...] = ()
    actions_performed: tuple[PerformedAction, ...] = ()


def search_result_evidence(
    result: ToolResult[PickSearchResponse],
) -> ToolEvidenceBundle:
    if not result.success or result.data is None:
        unavailable = result.user_safe_message or (
            "No se pudo confirmar la búsqueda en BuenPick."
        )
        return ToolEvidenceBundle(
            unavailable_data=(unavailable,),
            actions_performed=(
                PerformedAction(name="search_available_picks", outcome="failed"),
            ),
        )

    action = PerformedAction(name="search_available_picks", outcome="succeeded")
    if not result.data.items:
        return ToolEvidenceBundle(
            confirmed_data=(
                EvidenceItem(
                    label="search_availability",
                    value="BuenPick returned no available picks for this search.",
                    source=EvidenceSource.BUENPICK_INTERNAL_API,
                ),
            ),
            actions_performed=(action,),
        )

    evidence = tuple(
        EvidenceItem(
            label=f"available_pick_{index}",
            value=(
                f"Title: {pick.title}; Commerce: {pick.commerce.name}; "
                f"Price ARS: {format_ars_cents(pick.price)}; "
                f"Available quantity: {pick.available_quantity}; "
                "Status: available"
            ),
            source=EvidenceSource.BUENPICK_INTERNAL_API,
            source_reference=pick.id,
        )
        for index, pick in enumerate(result.data.items, start=1)
    )
    unavailable_data = (
        ("El contenido exacto de una bolsa sorpresa no está confirmado por BuenPick.",)
        if any("sorpresa" in pick.title.casefold() for pick in result.data.items)
        else ()
    )
    return ToolEvidenceBundle(
        confirmed_data=evidence,
        unavailable_data=unavailable_data,
        actions_performed=(action,),
    )


def order_result_evidence(
    result: ToolResult[CustomerOrder],
) -> ToolEvidenceBundle:
    if not result.success or result.data is None:
        unavailable = result.user_safe_message or (
            "No se pudo confirmar una orden perteneciente a esta persona."
        )
        return ToolEvidenceBundle(
            unavailable_data=(unavailable,),
            actions_performed=(
                PerformedAction(name="get_customer_order", outcome="failed"),
            ),
        )

    order = result.data
    evidence: list[EvidenceItem] = [
        EvidenceItem(
            label="order_status",
            value=order.status,
            source=EvidenceSource.BUENPICK_INTERNAL_API,
            source_reference=order.id,
        ),
        EvidenceItem(
            label="order_commerce",
            value=order.commerce.name,
            source=EvidenceSource.BUENPICK_INTERNAL_API,
            source_reference=order.id,
        ),
        EvidenceItem(
            label="order_total_ars",
            value=format_ars_cents(order.total),
            source=EvidenceSource.BUENPICK_INTERNAL_API,
            source_reference=order.id,
        ),
        EvidenceItem(
            label="fulfillment_type",
            value=order.fulfillment.type,
            source=EvidenceSource.BUENPICK_INTERNAL_API,
            source_reference=order.id,
        ),
    ]
    evidence.extend(
        EvidenceItem(
            label=f"order_pick_{index}",
            value=(
                f"Title: {pick.title}; Quantity: {pick.quantity}; "
                f"Line total ARS: {format_ars_cents(pick.line_total)}"
            ),
            source=EvidenceSource.BUENPICK_INTERNAL_API,
            source_reference=order.id,
        )
        for index, pick in enumerate(order.picks, start=1)
    )
    if order.fulfillment.pickup_code:
        evidence.append(
            EvidenceItem(
                label="pickup_code",
                value=order.fulfillment.pickup_code,
                source=EvidenceSource.BUENPICK_INTERNAL_API,
                source_reference=order.id,
            )
        )
    if order.pickup.instructions:
        evidence.append(
            EvidenceItem(
                label="pickup_instructions",
                value=order.pickup.instructions,
                source=EvidenceSource.BUENPICK_INTERNAL_API,
                source_reference=order.id,
            )
        )
    evidence.append(
        EvidenceItem(
            label="pickup_store_address",
            value=order.pickup.store_address,
            source=EvidenceSource.BUENPICK_INTERNAL_API,
            source_reference=order.id,
        )
    )
    return ToolEvidenceBundle(
        confirmed_data=tuple(evidence),
        actions_performed=(
            PerformedAction(name="get_customer_order", outcome="succeeded"),
        ),
    )
