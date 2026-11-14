from __future__ import annotations

from app.rag.models import Chunk


def chunk_table(table, tenant_id: str) -> list[Chunk]:
    """One parent plus column groups of 15. Children carry the table name."""
    columns = sorted(
        [column for column in table.columns if column.is_active],
        key=lambda column: column.ordinal_position or 0,
    )
    header = f"TABLE: {table.schema_name}.{table.table_name}"
    if table.description:
        header += f"\nDescription: {table.description}"
    parent_id = f"schema:{table.id}:parent"
    parent = Chunk(
        id=parent_id,
        text=header + "\nCOLUMNS: " + ", ".join(column.column_name for column in columns),
        parent_id=None,
        object_type="schema_parent",
        tenant_id=tenant_id,
        source_id=str(table.source_id),
        table_id=str(table.id),
        section_path=f"{table.schema_name}.{table.table_name}",
    )
    children: list[Chunk] = []
    for group_index in range(0, max(len(columns), 1), 15):
        group = columns[group_index:group_index + 15]
        if not group and columns:
            continue
        lines = [header, "COLUMNS:"]
        for column in group:
            detail = column.data_type
            if column.business_name:
                detail += f"; business name: {column.business_name}"
            if column.description:
                detail += f"; description: {column.description}"
            lines.append(f"- {column.column_name} ({detail})")
        children.append(
            Chunk(
                id=f"schema:{table.id}:c{group_index // 15}",
                text="\n".join(lines),
                parent_id=parent_id,
                object_type="schema_child",
                tenant_id=tenant_id,
                source_id=str(table.source_id),
                table_id=str(table.id),
                section_path=parent.section_path,
            )
        )
    return [parent, *children]