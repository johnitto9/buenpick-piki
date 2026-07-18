from enum import StrEnum
from types import MappingProxyType

from pydantic import model_validator

from piki.domain.contracts import (
    ContextPacket,
    ContractModel,
    EvidenceItem,
    PerformedAction,
    ResponseMode,
)


class PolicyName(StrEnum):
    DISCOVER_PICKS = "discover_picks"
    PICK_DETAIL = "pick_detail"
    COMMERCE_INFO = "commerce_info"
    ORDER_STATUS = "order_status"
    PICK_IMAGE = "pick_image"
    HUMAN_HANDOFF = "human_handoff"
    EXPLAIN_BUENPICK = "explain_buenpick"


class ToolName(StrEnum):
    SEARCH_AVAILABLE_PICKS = "search_available_picks"
    GET_AVAILABLE_PICK = "get_available_pick"
    GET_COMMERCE = "get_commerce"
    GET_CUSTOMER_ORDER = "get_customer_order"
    GET_PICK_IMAGE = "get_pick_image"
    REQUEST_HUMAN_HANDOFF = "request_human_handoff"


class PolicyDefinition(ContractModel):
    name: PolicyName
    task: str
    response_mode: ResponseMode
    allowed_tools: tuple[ToolName, ...] = ()
    writing_rules: tuple[str, ...] = ()
    commercial: bool = False
    requires_confirmed_evidence: bool = False

    @model_validator(mode="after")
    def validate_commercial_route(self) -> "PolicyDefinition":
        if self.commercial:
            if self.response_mode is ResponseMode.NON_COMMERCIAL_LLM:
                raise ValueError("commercial policy cannot use non-commercial LLM mode")
            if not self.requires_confirmed_evidence:
                raise ValueError("commercial policy must require confirmed evidence")
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("policy tools must be unique")
        return self

    def context_packet(
        self,
        *,
        query: str,
        trace_id: str,
        confirmed_data: tuple[EvidenceItem, ...] = (),
        unavailable_data: tuple[str, ...] = (),
        actions_performed: tuple[PerformedAction, ...] = (),
        active_pick_id: str | None = None,
    ) -> ContextPacket:
        if self.requires_confirmed_evidence and not confirmed_data:
            raise ValueError(f"policy {self.name.value} requires confirmed evidence")
        return ContextPacket(
            task=self.task,
            query=query,
            confirmed_data=confirmed_data,
            unavailable_data=unavailable_data,
            actions_performed=actions_performed,
            writing_rules=self.writing_rules,
            response_mode=self.response_mode,
            active_pick_id=active_pick_id,
            trace_id=trace_id,
        )


_POLICIES = {
    PolicyName.DISCOVER_PICKS: PolicyDefinition(
        name=PolicyName.DISCOVER_PICKS,
        task="Ayudar a descubrir picks de alimentos disponibles en BuenPick.",
        response_mode=ResponseMode.JINJA_LLM,
        allowed_tools=(ToolName.SEARCH_AVAILABLE_PICKS,),
        writing_rules=(
            "Presentar únicamente picks devueltos como disponibles.",
            "Distinguir una búsqueda sin resultados de un error de la fuente.",
            "No prometer el contenido exacto de una bolsa sorpresa.",
            "Cerrar con un único próximo paso útil.",
        ),
        commercial=True,
        requires_confirmed_evidence=True,
    ),
    PolicyName.PICK_DETAIL: PolicyDefinition(
        name=PolicyName.PICK_DETAIL,
        task="Explicar un pick disponible y cómo continuar el rescate en BuenPick.",
        response_mode=ResponseMode.JINJA_LLM,
        allowed_tools=(ToolName.GET_AVAILABLE_PICK,),
        writing_rules=(
            "Usar precio, disponibilidad, retiro, imagen y enlace sólo si están confirmados.",
            "Aclarar los datos no disponibles sin completarlos por contexto.",
            "Dirigir a la URL pública confirmada; no crear checkout dentro de Piki.",
        ),
        commercial=True,
        requires_confirmed_evidence=True,
    ),
    PolicyName.COMMERCE_INFO: PolicyDefinition(
        name=PolicyName.COMMERCE_INFO,
        task="Explicar datos operativos confirmados de un comercio BuenPick.",
        response_mode=ResponseMode.JINJA_LLM,
        allowed_tools=(ToolName.GET_COMMERCE,),
        writing_rules=(
            "No inferir horarios, cobertura o entrega desde la descripción del comercio.",
            "Separar claramente retiro de entrega.",
        ),
        commercial=True,
        requires_confirmed_evidence=True,
    ),
    PolicyName.ORDER_STATUS: PolicyDefinition(
        name=PolicyName.ORDER_STATUS,
        task="Informar el estado confirmado de una orden perteneciente a la persona.",
        response_mode=ResponseMode.JINJA_LLM,
        allowed_tools=(ToolName.GET_CUSTOMER_ORDER,),
        writing_rules=(
            "No revelar una orden sin prueba de pertenencia validada por BuenPick.",
            "No reinterpretar el estado ni inventar fechas o códigos de retiro.",
            "No repetir datos de pertenencia en la respuesta.",
        ),
        commercial=True,
        requires_confirmed_evidence=True,
    ),
    PolicyName.PICK_IMAGE: PolicyDefinition(
        name=PolicyName.PICK_IMAGE,
        task="Preparar la imagen confirmada del pick activo.",
        response_mode=ResponseMode.DETERMINISTIC,
        allowed_tools=(ToolName.GET_AVAILABLE_PICK, ToolName.GET_PICK_IMAGE),
        writing_rules=(
            "Usar sólo la imagen del pick reconfirmado.",
            "Si no hay imagen, informar la limitación sin simular un envío.",
        ),
        commercial=True,
        requires_confirmed_evidence=True,
    ),
    PolicyName.HUMAN_HANDOFF: PolicyDefinition(
        name=PolicyName.HUMAN_HANDOFF,
        task="Confirmar de forma determinista la solicitud de atención humana.",
        response_mode=ResponseMode.DETERMINISTIC,
        allowed_tools=(ToolName.REQUEST_HUMAN_HANDOFF,),
        writing_rules=("No afirmar que una persona respondió hasta que exista ese evento.",),
    ),
    PolicyName.EXPLAIN_BUENPICK: PolicyDefinition(
        name=PolicyName.EXPLAIN_BUENPICK,
        task="Explicar de forma breve cómo BuenPick ayuda a rescatar alimentos.",
        response_mode=ResponseMode.NON_COMMERCIAL_LLM,
        writing_rules=(
            "Explicar el concepto sin afirmar que existe un pick concreto.",
            "No afirmar presencia ni ausencia actual de picks sin consultar BuenPick.",
            "No convertir la explicación en un catálogo estable.",
        ),
    ),
}

POLICIES = MappingProxyType(_POLICIES)


def get_policy(name: PolicyName) -> PolicyDefinition:
    return POLICIES[name]
