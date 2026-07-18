import re
from enum import StrEnum

from pydantic import model_validator

from piki.domain.contracts import (
    ContextPacket,
    ContractModel,
    EvidenceSource,
    ResponseMode,
)


class GroundingFailure(StrEnum):
    EMPTY = "empty"
    INTERNAL_LEAK = "internal_leak"
    UNSUPPORTED_HIGH_RISK_FACT = "unsupported_high_risk_fact"
    UNAVAILABLE_CONTENT_CLAIM = "unavailable_content_claim"
    INTERNAL_REFERENCE = "internal_reference"
    EVIDENCE_FREE_COMMERCIAL_CLAIM = "evidence_free_commercial_claim"


class GroundingResult(ContractModel):
    safe: bool
    text: str | None = None
    failures: tuple[GroundingFailure, ...] = ()

    @model_validator(mode="after")
    def validate_shape(self) -> "GroundingResult":
        if self.safe != (self.text is not None and not self.failures):
            raise ValueError("safe grounding results require text and no failures")
        if not self.safe and not self.failures:
            raise ValueError("blocked grounding results require a failure")
        return self


_INTERNAL_PATTERNS = (
    "DATOS CONFIRMADOS",
    "DATOS NO DISPONIBLES",
    "ACCIONES REALIZADAS",
    "REGLAS DE REDACCIÓN",
    "SYSTEM PROMPT",
    "TRACE_ID",
    "BUENPICK_INTERNAL_API",
    "<TOOLS>",
    "TOOL_RESULT",
)
_HIGH_RISK_PATTERNS = (
    re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE),
    re.compile(r"(?:ARS\s*)?\$\s*\d[\d.]*?(?:,\d{1,2})?(?=\s|$|[).,;:!?])", re.IGNORECASE),
    re.compile(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b"),
    re.compile(r"\b\d+(?:[.,]\d+)*\b"),
)
_CONTENT_CLAIM = re.compile(
    r"\b(?:incluye|contiene|trae|viene\s+con|est[áa]\s+compuest[oa])\b",
    re.IGNORECASE,
)
_EVIDENCE_FREE_AVAILABILITY = re.compile(
    r"\b(?:no\s+(?:tengo|hay|encontr[eé])(?:\s+\w+){0,3}\s+"
    r"(?:rescate|pick|opci[oó]n)|(?:hay|encontr[eé])(?:\s+\w+){0,5}\s+"
    r"(?:disponibles?|para\s+rescatar))\b",
    re.IGNORECASE,
)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _safe_fallback_value(value: str) -> str:
    compact = " ".join(value.split())
    upper_value = compact.upper()
    if any(pattern in upper_value for pattern in _INTERNAL_PATTERNS):
        return "[dato omitido por seguridad]"
    return compact


class GroundingValidator:
    def validate(self, text: str, packet: ContextPacket) -> GroundingResult:
        candidate = text.strip()
        failures: set[GroundingFailure] = set()
        if not candidate:
            failures.add(GroundingFailure.EMPTY)

        upper_candidate = candidate.upper()
        if any(pattern in upper_candidate for pattern in _INTERNAL_PATTERNS):
            failures.add(GroundingFailure.INTERNAL_LEAK)

        evidence_values = tuple(item.value for item in packet.confirmed_data)
        evidence_corpus = _normalized("\n".join(evidence_values))
        has_api_evidence = any(
            item.source is EvidenceSource.BUENPICK_INTERNAL_API
            for item in packet.confirmed_data
        )
        if not has_api_evidence and _EVIDENCE_FREE_AVAILABILITY.search(candidate):
            failures.add(GroundingFailure.EVIDENCE_FREE_COMMERCIAL_CLAIM)
        for pattern in _HIGH_RISK_PATTERNS:
            for match in pattern.finditer(candidate):
                token = _normalized(match.group(0).rstrip(".,;:!?)"))
                if token and token not in evidence_corpus:
                    failures.add(GroundingFailure.UNSUPPORTED_HIGH_RISK_FACT)

        unavailable = _normalized("\n".join(packet.unavailable_data))
        if "contenido" in unavailable and _CONTENT_CLAIM.search(candidate):
            failures.add(GroundingFailure.UNAVAILABLE_CONTENT_CLAIM)

        for item in packet.confirmed_data:
            reference = item.source_reference
            if (
                reference
                and _normalized(reference) in _normalized(candidate)
                and _normalized(reference) not in evidence_corpus
            ):
                failures.add(GroundingFailure.INTERNAL_REFERENCE)

        if failures:
            return GroundingResult(
                safe=False,
                failures=tuple(sorted(failures, key=lambda item: item.value)),
            )
        return GroundingResult(safe=True, text=candidate)


def factual_fallback(packet: ContextPacket) -> str:
    api_evidence = tuple(
        item
        for item in packet.confirmed_data
        if item.source is EvidenceSource.BUENPICK_INTERNAL_API
    )
    if not api_evidence:
        if packet.response_mode is ResponseMode.NON_COMMERCIAL_LLM:
            return (
                "Soy Piki, el asistente de BuenPick. Te ayudo a descubrir alimentos "
                "para rescatar y a consultar información confirmada por BuenPick."
            )
        return (
            "No pude confirmar la información necesaria en este momento. "
            "Probemos de nuevo en un rato."
        )

    lines = ["Esto es lo que pude confirmar:"]
    lines.extend(
        f"- {_safe_fallback_value(item.label)}: {_safe_fallback_value(item.value)}"
        for item in api_evidence[:8]
    )
    if packet.unavailable_data:
        lines.append("Hay datos que todavía no pude confirmar.")
    return "\n".join(lines)[:4096]
