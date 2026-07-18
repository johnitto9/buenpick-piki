from typing import Protocol

from pydantic import HttpUrl, model_validator

from piki.domain.contracts import (
    ContractModel,
    EvidenceItem,
    EvidenceSource,
    PerformedAction,
    ToolErrorCode,
    ToolResult,
)
from piki.state.active_pick import (
    ActivePickResolution,
    ActivePickResolutionStatus,
    ConversationScope,
)
from piki.tools.buenpick import PickImageEvidence


class ActivePickResolver(Protocol):
    async def resolve(
        self, scope: ConversationScope, *, explicit_pick_id: str | None = None
    ) -> ActivePickResolution: ...


class PickImageTool(Protocol):
    async def get_pick_image(
        self, *, pick_id: str, trace_id: str
    ) -> ToolResult[PickImageEvidence]: ...


class PickImagePreparation(ContractModel):
    success: bool
    active_pick_id: str | None = None
    media_url: HttpUrl | None = None
    confirmed_data: tuple[EvidenceItem, ...] = ()
    actions_performed: tuple[PerformedAction, ...] = ()
    error_code: ToolErrorCode | None = None
    user_safe_message: str | None = None
    trace_id: str

    @model_validator(mode="after")
    def validate_shape(self) -> "PickImagePreparation":
        if self.success:
            if (
                self.active_pick_id is None
                or self.media_url is None
                or not self.confirmed_data
                or self.error_code is not None
                or self.user_safe_message is not None
            ):
                raise ValueError("successful image preparation requires confirmed media")
        elif self.error_code is None or not self.user_safe_message:
            raise ValueError("failed image preparation requires a safe error")
        return self


class PickImagePreparer:
    def __init__(
        self,
        active_picks: ActivePickResolver,
        image_tool: PickImageTool,
    ) -> None:
        self._active_picks = active_picks
        self._image_tool = image_tool

    async def prepare(
        self,
        scope: ConversationScope,
        *,
        trace_id: str,
    ) -> PickImagePreparation:
        resolution = await self._active_picks.resolve(scope)
        if resolution.status is not ActivePickResolutionStatus.CONFIRMED:
            return self._resolution_failure(resolution, trace_id)
        if resolution.pick is None:
            raise AssertionError("confirmed active pick requires pick evidence")

        image_result = await self._image_tool.get_pick_image(
            pick_id=resolution.pick.id,
            trace_id=trace_id,
        )
        if not image_result.success or image_result.data is None:
            return PickImagePreparation(
                success=False,
                error_code=image_result.error_code or ToolErrorCode.INTERNAL_ERROR,
                user_safe_message=image_result.user_safe_message
                or "No pude confirmar una imagen para ese pick.",
                actions_performed=(
                    PerformedAction(name="get_pick_image", outcome="failed"),
                ),
                trace_id=trace_id,
            )

        image = image_result.data
        return PickImagePreparation(
            success=True,
            active_pick_id=image.pick_id,
            media_url=image.image_url,
            confirmed_data=(
                EvidenceItem(
                    label="pick_title",
                    value=image.title,
                    source=EvidenceSource.BUENPICK_INTERNAL_API,
                    source_reference=image.pick_id,
                ),
                EvidenceItem(
                    label="pick_image_url",
                    value=str(image.image_url),
                    source=EvidenceSource.BUENPICK_INTERNAL_API,
                    source_reference=image.pick_id,
                ),
            ),
            actions_performed=(
                PerformedAction(name="get_available_pick", outcome="succeeded"),
                PerformedAction(name="get_pick_image", outcome="succeeded"),
            ),
            trace_id=trace_id,
        )

    @staticmethod
    def _resolution_failure(
        resolution: ActivePickResolution,
        trace_id: str,
    ) -> PickImagePreparation:
        failures = {
            ActivePickResolutionStatus.MISSING: (
                ToolErrorCode.BAD_REQUEST,
                "Elegí un pick disponible antes de pedirme la foto.",
            ),
            ActivePickResolutionStatus.STALE: (
                ToolErrorCode.NOT_FOUND,
                "Ese pick ya no está disponible. Busquemos otra opción para rescatar.",
            ),
            ActivePickResolutionStatus.STATE_UNAVAILABLE: (
                ToolErrorCode.UPSTREAM_UNAVAILABLE,
                "No pude recuperar el pick de esta conversación. Decime cuál querías ver.",
            ),
            ActivePickResolutionStatus.UPSTREAM_UNAVAILABLE: (
                resolution.error_code or ToolErrorCode.UPSTREAM_UNAVAILABLE,
                "No pude confirmar la disponibilidad ni la imagen en este momento.",
            ),
        }
        error_code, message = failures[resolution.status]
        return PickImagePreparation(
            success=False,
            error_code=error_code,
            user_safe_message=message,
            actions_performed=(
                PerformedAction(name="get_available_pick", outcome="failed"),
            ),
            trace_id=trace_id,
        )
