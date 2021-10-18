from dataclasses import dataclass, field

from tickit.devices.eiger.eiger_schema import rw_str


@dataclass
class StreamConfig:
    """Eiger stream configuration taken from the API spec."""

    mode: str = field(
        default="enabled", metadata=rw_str(allowed_values=["disabled", "enabled"])
    )
    header_detail: str = field(
        default="basic", metadata=rw_str(allowed_values=["all", "basic", "none"])
    )
    header_appendix: str = field(default="", metadata=rw_str())
    image_appendix: str = field(default="", metadata=rw_str())
