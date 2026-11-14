from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Chunk:
    id: str
    text: str
    parent_id: str | None
    object_type: str
    tenant_id: str
    source_id: str | None = None
    domain_id: str | None = None
    document_id: str | None = None
    table_id: str | None = None
    section_path: str = ""
    file_name: str = ""
    distance: float | None = None
    score: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalScope:
    tenant_id: str
    source_id: str | None = None
    domain_id: str | None = None
    object_types: list[str] | None = None
    table_ids: list[str] | None = None