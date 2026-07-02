"""Provenance metadata stamped on every event."""

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    """Records how and by which software version evidence was captured."""

    source: str = Field(description="Exchange or system source identifier")
    adapter_version: str
    pipeline_version: str = Field(description="Evidence pipeline version")
    schema_version: int = Field(default=1, description="EventEnvelope schema version")

    model_config = {"frozen": True}
