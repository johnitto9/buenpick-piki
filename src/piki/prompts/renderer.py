import json
from importlib.resources import files

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from piki.domain.contracts import ContextPacket


def _json_string(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


class PromptAssets:
    evidence_template_name = "evidence.txt.j2"

    def __init__(self) -> None:
        self._environment = Environment(
            loader=PackageLoader("piki.prompts", "templates"),
            undefined=StrictUndefined,
            autoescape=select_autoescape(
                disabled_extensions=("j2",),
                default_for_string=True,
                default=True,
            ),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        self._environment.filters["json_string"] = _json_string

    @property
    def system_prompt(self) -> str:
        return (
            files("piki.prompts")
            .joinpath("system_prompt.txt")
            .read_text(encoding="utf-8")
            .strip()
        )

    def render_evidence(self, packet: ContextPacket) -> str:
        template = self._environment.get_template(self.evidence_template_name)
        return template.render(packet=packet).strip()
