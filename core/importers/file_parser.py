import csv
import io
import re

REQUIRED_COLUMNS = {"name", "email"}
OPTIONAL_COLUMNS = {"title", "linkedin_url", "location", "company"}
ALL_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_row(row: dict, row_num: int) -> list[str]:
    errors = []
    if not row.get("name", "").strip():
        errors.append(f"Row {row_num}: missing 'name'")
    if not row.get("email", "").strip():
        errors.append(f"Row {row_num}: missing 'email'")
    elif not EMAIL_RE.match(row["email"].strip()):
        errors.append(f"Row {row_num}: invalid email '{row['email'].strip()}'")
    return errors


def _normalize_row(row: dict, source: str) -> dict:
    return {
        "name": row.get("name", "").strip(),
        "email": row.get("email", "").strip().lower(),
        "title": row.get("title", "").strip() or None,
        "linkedin_url": row.get("linkedin_url", "").strip() or None,
        "location": row.get("location", "").strip() or None,
        "company": row.get("company", "").strip() or None,
        "source": source,
    }


def _validate_headers(headers: list[str]) -> list[str]:
    errors = []
    normalized = [h.strip().lower() for h in headers]
    for req in REQUIRED_COLUMNS:
        if req not in normalized:
            errors.append(f"Missing required column: '{req}'")
    return errors


def parse_csv(file_obj) -> tuple[list[dict], list[str]]:
    errors = []
    valid_rows = []

    content = file_obj.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        return [], ["Empty CSV file or no headers found"]

    header_errors = _validate_headers(list(reader.fieldnames))
    if header_errors:
        return [], header_errors

    for i, row in enumerate(reader, start=2):
        normalized = {k.strip().lower(): v for k, v in row.items() if k}
        row_errors = validate_row(normalized, i)
        if row_errors:
            errors.extend(row_errors)
        else:
            valid_rows.append(_normalize_row(normalized, "csv_import"))

    return valid_rows, errors


def parse_xlsx(file_obj) -> tuple[list[dict], list[str]]:
    import openpyxl

    errors = []
    valid_rows = []

    wb = openpyxl.load_workbook(file_obj, read_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        wb.close()
        return [], ["Empty spreadsheet or no headers found"]

    headers = [str(h).strip().lower() if h else "" for h in header_row]
    header_errors = _validate_headers(headers)
    if header_errors:
        wb.close()
        return [], header_errors

    for i, row in enumerate(rows_iter, start=2):
        row_dict = {}
        for j, val in enumerate(row):
            if j < len(headers) and headers[j]:
                row_dict[headers[j]] = str(val).strip() if val is not None else ""
        if not any(row_dict.values()):
            continue
        row_errors = validate_row(row_dict, i)
        if row_errors:
            errors.extend(row_errors)
        else:
            valid_rows.append(_normalize_row(row_dict, "xlsx_import"))

    wb.close()
    return valid_rows, errors


def parse_import_file(file_obj, filename: str) -> tuple[list[dict], list[str]]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        return parse_csv(file_obj)
    elif ext in ("xlsx", "xls"):
        return parse_xlsx(file_obj)
    else:
        return [], [f"Unsupported file format: '.{ext}'. Please upload a .csv or .xlsx file."]
