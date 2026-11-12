import csv
import io
from django.http import StreamingHttpResponse

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_import_cell(val):
    """
    Cleans imported cell values before saving to prevent formula injection.
    Prefixes with ' if the value starts with =, +, -, @, \\t, or \\r.
    """
    if val is None:
        return ""
    s = str(val).strip()
    if s and s.startswith(FORMULA_PREFIXES):
        return "'" + s
    return s


def sanitize_export_cell(val):
    """
    Cleans cell values for CSV export to protect spreadsheet programs (Excel, LibreOffice,
    Google Sheets) against formula injection.
    Prefixes with ' if the value starts with =, +, -, @, \\t, or \\r.
    """
    if val is None:
        return ""
    s = str(val)
    if s and s.startswith(FORMULA_PREFIXES):
        return "'" + s
    return s


def decode_csv_file(uploaded_file):
    """
    Decodes an uploaded CSV file, handling UTF-8 with or without BOM (utf-8-sig),
    and falling back to latin-1 / cp1252 for files exported from legacy Excel.
    """
    raw_bytes = uploaded_file.read()
    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw_bytes.decode("latin-1")
    return content


class Echo:
    """
    An object that implements the write method of a file-like interface,
    returning the string directly to stream CSV without buffering all data in memory.
    """
    def write(self, value):
        return value


def stream_csv_response(filename, headers, row_generator):
    """
    Streams a CSV file as a StreamingHttpResponse so large datasets don't consume memory.
    Every cell is sanitized against CSV formula injection.
    """
    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)

    def generate_csv_rows():
        # Header row
        yield writer.writerow([sanitize_export_cell(h) for h in headers])
        # Data rows
        for row in row_generator:
            yield writer.writerow([sanitize_export_cell(item) for item in row])

    response = StreamingHttpResponse(generate_csv_rows(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

