from __future__ import annotations

import re
import uuid

from app.rag.models import Chunk

_HEADING = re.compile(r"^(#{1,6}\s+.+|=== Sheet:.+|--- Page \d+ ---)\s*$")


def _children(parent_text: str, size: int = 700, overlap: int = 80) -> list[str]:
    text = parent_text.strip()
    if not text:
        return []
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            break_at = text.rfind("\n", start, end)
            if break_at <= start + size // 2:
                break_at = text.rfind(" ", start, end)
            if break_at > start:
                end = break_at
        piece = text[start:end].strip()
        if piece:
            parts.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return parts


def chunk_document(
    *,
    text: str,
    tenant_id: str,
    domain_id: str,
    document_id: str,
    file_name: str,
    source_id: str | None,
) -> list[Chunk]:
    """Parent per heading, page, or sheet. Only children are embedded."""
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    title = "Document"
    body: list[str] = []
    for line in lines:
        if _HEADING.match(line.strip()):
            if body or sections:
                sections.append((title, body))
            title = line.strip()
            body = []
        else:
            body.append(line)
    sections.append((title, body))

    chunks: list[Chunk] = []
    for index, (heading, content_lines) in enumerate(sections):
        parent_body = "\n".join(content_lines).strip()
        if not parent_body:
            continue
        parent_id = f"domain:{domain_id}:doc:{document_id}:p{index}"
        header = heading if heading.startswith("#") or heading.startswith("=") or heading.startswith("-") else heading
        for child_index, child in enumerate(_children(parent_body)):
            child_text = f"{header}\n{child}".strip()
            chunks.append(
                Chunk(
                    id=f"{parent_id}:c{child_index}",
                    text=child_text,
                    parent_id=parent_id,
                    object_type="domain_child",
                    tenant_id=tenant_id,
                    source_id=source_id,
                    domain_id=domain_id,
                    document_id=document_id,
                    section_path=heading[:240],
                    file_name=file_name,
                )
            )
    return chunks