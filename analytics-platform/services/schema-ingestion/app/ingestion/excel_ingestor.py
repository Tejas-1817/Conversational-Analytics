"""Excel (.xlsx) to SQLite materialization and preview engine.

Converts multi-sheet Excel workbooks into a clean, local SQLite database
(one table per sheet) with identifier sanitization, duplicate resolution,
mixed-type coercion, and read-only compatibility.
"""
import io
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import structlog
import pandas as pd

log = structlog.get_logger(__name__)


def sanitize_identifier(name: str, max_length: int = 63) -> str:
    """Sanitizes sheet and column names to safe SQL identifiers (PostgreSQL/SQLite safe).
    
    1. Lowercases the string.
    2. Preserves pandas duplicate markers (.1, .2 -> _1, _2).
    3. Replaces non-alphanumeric characters with underscores.
    4. Strips leading digits or underscores.
    5. Collapses multiple consecutive underscores.
    6. Truncates to max_length (default 63).
    """
    if not name or not str(name).strip():
        return "unnamed_column"
    
    s = str(name).strip()

    # Preserve pandas disambiguation for duplicate columns (.1, .2 -> _1, _2)
    s = re.sub(r'\.(\d+)$', r'_\1', s)

    # Convert to lowercase
    s = s.lower()

    # Replace all non-alphanumeric characters with underscores
    s = re.sub(r'[^a-z0-9_]', '_', s)

    # Strip leading digits or underscores to make a valid SQL identifier
    s = re.sub(r'^[^a-z]+', '', s)

    # Collapse multiple underscores into one
    s = re.sub(r'_+', '_', s)
    s = s.strip('_')

    if not s:
        s = "col"

    return s[:max_length]


def sanitize_column_names(columns: List[Any]) -> List[str]:
    """Sanitizes a list of column names, ensuring no collision within the table."""
    seen: Dict[str, int] = {}
    clean_cols: List[str] = []

    for idx, raw_col in enumerate(columns):
        base_name = sanitize_identifier(str(raw_col) if raw_col is not None else f"col_{idx+1}")
        if not base_name:
            base_name = f"col_{idx+1}"

        if base_name in seen:
            seen[base_name] += 1
            col_name = f"{base_name}_{seen[base_name]}"
        else:
            seen[base_name] = 1
            col_name = base_name

        clean_cols.append(col_name)

    return clean_cols


def preview_excel_sheets(
    file_source: Union[str, Path, bytes, io.BytesIO],
    max_preview_rows: int = 5
) -> Dict[str, Any]:
    """Inspects an uploaded Excel file and returns sheet previews without materializing to SQLite."""
    if isinstance(file_source, (bytes, bytearray)):
        file_obj = io.BytesIO(file_source)
    else:
        file_obj = file_source

    excel_file = pd.ExcelFile(file_obj, engine="openpyxl")
    sheet_previews = []
    seen_table_names: Dict[str, int] = {}

    for sheet_name in excel_file.sheet_names:
        # Suggested table name
        raw_tbl_name = sanitize_identifier(sheet_name)
        if not raw_tbl_name:
            raw_tbl_name = "sheet"
        
        if raw_tbl_name in seen_table_names:
            seen_table_names[raw_tbl_name] += 1
            suggested_tbl_name = f"{raw_tbl_name}_{seen_table_names[raw_tbl_name]}"
        else:
            seen_table_names[raw_tbl_name] = 1
            suggested_tbl_name = raw_tbl_name

        try:
            # Read top rows for fast preview
            df_preview = pd.read_excel(
                excel_file,
                sheet_name=sheet_name,
                header=0,
                nrows=max_preview_rows
            )
            
            # Extract column names and clean them
            raw_columns = [str(c) for c in df_preview.columns]
            clean_columns = sanitize_column_names(raw_columns)
            
            # Format preview rows
            rows_data = []
            for _, row in df_preview.iterrows():
                row_dict = {}
                for col_idx, col_name in enumerate(clean_columns):
                    val = row.iloc[col_idx]
                    if pd.isna(val):
                        row_dict[col_name] = None
                    elif isinstance(val, pd.Timestamp):
                        row_dict[col_name] = val.isoformat()
                    else:
                        row_dict[col_name] = str(val) if not isinstance(val, (int, float, bool)) else val
                rows_data.append(row_dict)

            sheet_previews.append({
                "sheet_name": sheet_name,
                "suggested_table_name": suggested_tbl_name,
                "row_count": len(df_preview),
                "column_names": clean_columns,
                "suggested_header_row": 0,
                "preview_rows": rows_data,
                "is_empty": df_preview.empty or len(clean_columns) == 0
            })
        except Exception as exc:
            log.warning("excel_sheet_preview_failed", sheet_name=sheet_name, error=str(exc))
            sheet_previews.append({
                "sheet_name": sheet_name,
                "suggested_table_name": suggested_tbl_name,
                "row_count": 0,
                "column_names": [],
                "suggested_header_row": 0,
                "preview_rows": [],
                "is_empty": True,
                "warning": str(exc)
            })

    return {"sheets": sheet_previews}


def materialize_excel_to_sqlite(
    upload_path: Union[str, Path],
    sqlite_path: Union[str, Path],
    sheet_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Materializes an Excel workbook into a local SQLite database (one table per sheet)."""
    from sqlalchemy import create_engine
    
    upload_path = Path(upload_path).resolve()
    sqlite_path = Path(sqlite_path).resolve()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    if not upload_path.exists():
        raise FileNotFoundError(f"Excel upload file not found at: {upload_path}")

    sheet_overrides = sheet_overrides or {}
    
    # Remove existing SQLite file if re-materializing
    if sqlite_path.exists():
        try:
            sqlite_path.unlink()
        except Exception:
            pass

    log.info("starting_excel_materialization", upload_path=str(upload_path), sqlite_path=str(sqlite_path))

    excel_file = pd.ExcelFile(str(upload_path), engine="openpyxl")
    all_sheet_names = excel_file.sheet_names

    tables_ingested = []
    warnings: List[str] = []
    seen_table_names: Dict[str, int] = {}

    sqlite_engine = create_engine(f"sqlite:///{sqlite_path.as_posix()}")

    for sheet_name in all_sheet_names:
        sheet_str = str(sheet_name)
        overrides = sheet_overrides.get(sheet_str) or sheet_overrides.get(sheet_name) or {}
        
        # Check if sheet was excluded by user
        if overrides.get("include") is False:
            warnings.append(f"Sheet '{sheet_str}' was excluded by user override.")
            continue

        header_row = overrides.get("header_row", 0)
        try:
            header_row = int(header_row) if header_row is not None else 0
        except (ValueError, TypeError):
            header_row = 0
        
        # Read full sheet
        try:
            df = pd.read_excel(
                excel_file,
                sheet_name=sheet_name,
                header=header_row
            )
        except Exception as read_exc:
            err_msg = f"Failed to read sheet '{sheet_str}': {read_exc}"
            log.warning("excel_sheet_read_error", sheet_name=sheet_str, error=str(read_exc))
            warnings.append(err_msg)
            continue

        # Skip logic: only skip if sheet has zero columns at all
        if len(df.columns) == 0:
            warnings.append(f"Sheet '{sheet_str}' skipped: zero columns detected.")
            continue

        # Drop entirely empty blank rows if any
        if not df.empty:
            df = df.dropna(how="all")

        # Forward-fill columns if requested (for merged cell support)
        ffill_cols = overrides.get("forward_fill_columns") or []
        for fcol in ffill_cols:
            if fcol in df.columns:
                df[fcol] = df[fcol].ffill()

        # Sanitize table name
        custom_tbl_name = overrides.get("table_name")
        if custom_tbl_name and str(custom_tbl_name).strip():
            base_tbl_name = sanitize_identifier(str(custom_tbl_name).strip())
        else:
            base_tbl_name = sanitize_identifier(sheet_str)

        if not base_tbl_name:
            base_tbl_name = "sheet"

        if base_tbl_name in seen_table_names:
            seen_table_names[base_tbl_name] += 1
            table_name = f"{base_tbl_name}_{seen_table_names[base_tbl_name]}"
        else:
            seen_table_names[base_tbl_name] = 1
            table_name = base_tbl_name

        # Sanitize column names
        clean_columns = sanitize_column_names(list(df.columns))
        df.columns = clean_columns

        # Type handling: coerce object and timestamp types cleanly
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S").replace({pd.NaT: None})
            elif df[col].dtype == "object":
                df[col] = df[col].apply(lambda x: None if pd.isna(x) else str(x))

        # Write DataFrame to SQLite using SQLAlchemy engine
        try:
            df.to_sql(
                name=table_name,
                con=sqlite_engine,
                if_exists="replace",
                index=False
            )

            row_count = len(df)
            col_count = len(df.columns)
            tables_ingested.append({
                "table_name": table_name,
                "sheet_name": sheet_str,
                "row_count": row_count,
                "column_count": col_count,
                "columns": clean_columns,
                "warnings": []
            })
            log.info(
                "excel_sheet_materialized_to_sqlite",
                sheet_name=sheet_str,
                table_name=table_name,
                row_count=row_count,
                column_count=col_count
            )
        except Exception as write_exc:
            err_msg = f"Failed to write sheet '{sheet_str}' to table '{table_name}': {write_exc}"
            log.error("excel_sheet_write_error", sheet_name=sheet_str, table_name=table_name, error=str(write_exc))
            warnings.append(err_msg)

    sqlite_engine.dispose()

    if len(tables_ingested) == 0:
        raise ValueError(
            f"No valid sheets could be materialized from Excel file. Sheets found: {all_sheet_names}. Warnings: {warnings}"
        )

    stats = {
        "sheets_total": len(all_sheet_names),
        "sheets_ingested": len(tables_ingested),
        "sheets_skipped": len(all_sheet_names) - len(tables_ingested),
        "tables": tables_ingested,
        "warnings": warnings
    }
    return stats
