"""Excel 课表导入工具 - 解析 2026年总课表.xlsx"""
import re
from datetime import date, timedelta

# Monkey-patch openpyxl DataValidation to accept 'id' kwarg
# (compatibility fix for Excel files created with newer Office versions)
import openpyxl.worksheet.datavalidation as _dv
_original_dv_init = _dv.DataValidation.__init__
def _patched_dv_init(self, *args, **kwargs):
    kwargs.pop('id', None)
    _original_dv_init(self, *args, **kwargs)
_dv.DataValidation.__init__ = _patched_dv_init

import openpyxl


def _normalize_todo_text(value):
    """Normalize text fields so duplicate detection ignores whitespace noise."""
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value)).strip().casefold()


def _normalize_todo_date(value):
    if not value:
        return ''
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value).strip()


def build_todo_dedup_key(todo):
    """Build a stable business key for todo deduplication."""
    getter = getattr(todo, 'get', None)
    if callable(getter):
        get_value = lambda key, default=None: todo.get(key, default)
    else:
        get_value = lambda key, default=None: getattr(todo, key, default)

    return (
        _normalize_todo_text(get_value('title')),
        _normalize_todo_text(get_value('description')),
        _normalize_todo_text(get_value('responsible_person')),
        _normalize_todo_date(get_value('due_date')),
        int(get_value('priority', 2) or 2),
        _normalize_todo_text(get_value('notes')),
        get_value('schedule_id'),
        bool(get_value('is_completed', False)),
    )


def deduplicate_todo_payloads(todos):
    """
    Remove duplicate todo payloads before they are inserted into the database.
    Keeps the first occurrence for a given business key.
    """
    seen = set()
    deduplicated = []
    removed_count = 0

    for todo in todos:
        dedup_key = build_todo_dedup_key(todo)
        if dedup_key in seen:
            removed_count += 1
            continue
        seen.add(dedup_key)
        deduplicated.append(todo)

    return deduplicated, removed_count


def build_exact_todo_key(todo):
    """Build an exact field-level key for cleaning existing duplicated rows."""
    getter = getattr(todo, 'get', None)
    if callable(getter):
        get_value = lambda key, default=None: todo.get(key, default)
    else:
        get_value = lambda key, default=None: getattr(todo, key, default)

    return (
        get_value('title'),
        get_value('description'),
        get_value('responsible_person'),
        bool(get_value('is_completed', False)),
        get_value('due_date'),
        int(get_value('priority', 2) or 2),
        get_value('notes'),
        get_value('schedule_id'),
    )


def cleanup_existing_exact_duplicate_todos():
    """
    Delete exact duplicate todo rows from the database, keeping the earliest row.
    """
    from extensions import db
    from modules.oa.models import OATodo

    seen = {}
    removed_ids = []
    todos = OATodo.query.order_by(OATodo.id.asc()).all()

    for todo in todos:
        dedup_key = build_exact_todo_key(todo)
        if dedup_key in seen:
            removed_ids.append(todo.id)
            db.session.delete(todo)
            continue
        seen[dedup_key] = todo.id

    if removed_ids:
        db.session.commit()

    return {
        'total_before': len(todos),
        'removed_count': len(removed_ids),
        'kept_count': len(todos) - len(removed_ids),
        'removed_ids': removed_ids,
    }

MONTH_MAP = {
    '12月': 12, '1月': 1, '2月': 2, '3月': 3, '4月': 4, '5月': 5,
    '6月': 6, '7月': 7, '8月': 8, '9月': 9, '10月': 10, '11月': 11
}

# Time pattern: "10:00-12:00" or "10:00～12:00" or "10:00 - 12:00"
TIME_PATTERN = re.compile(
    r'(\d{1,2}[：:]\d{2})\s*[-~—]\s*(\d{1,2}[：:]\d{2})'
)


def parse_excel_date_serial(serial_number):
    """Convert Excel date serial number to Python date.
    Excel epoch: Jan 0, 1900 = serial 1, but with the Lotus 1-2-3 bug (1900 is treated as leap year).
    """
    base_date = date(1899, 12, 30)
    return base_date + timedelta(days=int(serial_number))


def normalize_time(t):
    """Normalize time string: replace Chinese colon, ensure HH:MM format."""
    t = t.replace('：', ':')
    parts = t.split(':')
    if len(parts) == 2:
        return f"{int(parts[0]):02d}:{parts[1]}"
    return t


def parse_course_cell(cell_value):
    """Parse a multi-line course cell into structured course entries.

    Typical format:
        10:00-12:00 胡老师
        帕金森键盘项目
        梁智健、薛明宇

    Some cells may contain multiple courses stacked or have slightly varied formats.
    Returns a list of dicts with keys: time_start, time_end, teacher, course_name, students
    """
    if not cell_value or not isinstance(cell_value, str):
        return []

    cell_value = cell_value.strip()
    if not cell_value:
        return []

    lines = [l.strip() for l in cell_value.split('\n') if l.strip()]
    courses = []
    i = 0

    while i < len(lines):
        line = lines[i]
        match = TIME_PATTERN.search(line)

        if match:
            time_start = normalize_time(match.group(1))
            time_end = normalize_time(match.group(2))

            # Teacher name: text after the time range on the same line
            after_time = line[match.end():].strip()
            teacher = after_time if after_time else ''

            # Course name and students from following lines
            course_name = ''
            students = ''

            # Collect non-time lines following this time entry
            j = i + 1
            extra_lines = []
            while j < len(lines):
                if TIME_PATTERN.search(lines[j]):
                    break
                extra_lines.append(lines[j])
                j += 1

            if extra_lines:
                course_name = extra_lines[0]
                if len(extra_lines) > 1:
                    students = extra_lines[1]
                # If teacher was empty, sometimes the teacher name is on the same line
                # as the time in a different format
                if not teacher and len(extra_lines) > 2:
                    # Check if first extra line looks like a teacher name (short, no special chars)
                    pass

            courses.append({
                'time_start': time_start,
                'time_end': time_end,
                'teacher': teacher,
                'course_name': course_name,
                'students': students
            })

            i = j
        else:
            i += 1

    return courses


def _fix_date_year(d, expected_year):
    """Correct the year of a parsed date if it doesn't match the expected year.

    Some sheets in the Excel file contain date serial numbers from a previous
    year's template, e.g. 2025-02-02 when 2026-02-02 is intended.
    """
    if d.year == expected_year:
        return d
    try:
        return d.replace(year=expected_year)
    except ValueError:
        # Feb 29 in non-leap year
        return date(expected_year, d.month, 28)


def _read_week_dates(row, expected_year):
    """Read 7 date values from the week separator row (columns A-G).

    Returns a list of 7 dates (or None for unreadable columns).
    Each column's serial number is parsed independently, so the week start
    day (Monday vs Sunday) is determined by the actual data.
    """
    week_dates = []
    for ci in range(7):
        if ci < len(row) and row[ci].value is not None:
            try:
                s = int(float(row[ci].value))
                if 40000 < s < 50000:
                    d = parse_excel_date_serial(s)
                    if expected_year:
                        d = _fix_date_year(d, expected_year)
                    week_dates.append(d)
                else:
                    week_dates.append(None)
            except (ValueError, TypeError):
                week_dates.append(None)
        else:
            week_dates.append(None)
    return week_dates


def import_schedule_from_excel(file_path, original_filename=None):
    """Parse the Excel schedule file into schedule and todo data.

    Handles two known quirks in the Excel template:
    1. Date serial numbers may be from a previous year (off by 365/730 days).
       We detect the intended year from the filename (e.g. "2026年总课表").
    2. Different sheets may start the week on different days (Monday or Sunday).
       We read all 7 date serials per week row to determine each column's date.

    Args:
        file_path: Path to the Excel file
        original_filename: Original uploaded filename (used to extract target year
            when file_path is a temp file)

    Returns:
        tuple: (schedules_list, todos_list)
    """
    import os
    wb = openpyxl.load_workbook(file_path, data_only=True)
    schedules = []
    todos = []

    # Extract target year from filename (e.g. "2026年总课表.xlsx" → 2026)
    filename = original_filename or os.path.basename(file_path)
    target_year = None
    year_match = re.search(r'(20\d{2})', filename)
    if year_match:
        target_year = int(year_match.group(1))

    for sheet_name in wb.sheetnames:
        if sheet_name not in MONTH_MAP:
            continue

        ws = wb[sheet_name]
        sheet_month = MONTH_MAP[sheet_name]

        # Determine expected year for this sheet
        expected_year = target_year
        if target_year and sheet_month == 12:
            expected_year = target_year - 1  # Dec belongs to previous year

        week_dates = None  # List of 7 dates for the current week block

        for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
            if len(row) < 7:
                continue

            # Check if this is a week separator row
            cell_a_val = row[0].value
            is_week_separator = False

            if cell_a_val is not None:
                try:
                    serial = int(float(cell_a_val))
                    if 40000 < serial < 50000:
                        week_dates = _read_week_dates(row, expected_year)
                        is_week_separator = True
                except (ValueError, TypeError):
                    pass

            if is_week_separator:
                continue

            if week_dates is None:
                continue

            # Process columns A-G using actual dates from separator row
            for col_idx in range(7):
                if col_idx >= len(row) or col_idx >= len(week_dates):
                    break

                course_date = week_dates[col_idx]
                if course_date is None:
                    continue

                cell = row[col_idx]
                if cell is None or cell.value is None:
                    continue

                cell_value = str(cell.value).strip()
                if not cell_value:
                    continue

                # Parse courses from cell
                parsed = parse_course_cell(cell_value)
                for c in parsed:
                    schedules.append({
                        'date': course_date,
                        'day_of_week': course_date.weekday(),
                        'time_start': c['time_start'],
                        'time_end': c['time_end'],
                        'teacher': c['teacher'],
                        'course_name': c['course_name'],
                        'students': c['students'],
                    })

            # Process column H (待办事项)
            if len(row) > 7:
                todo_cell = row[7]
                if todo_cell and todo_cell.value:
                    todo_text = str(todo_cell.value).strip()
                    if todo_text:
                        is_completed = False
                        if len(row) > 8 and row[8].value is not None:
                            try:
                                is_completed = bool(int(float(row[8].value)))
                            except (ValueError, TypeError):
                                pass

                        person = ''
                        if len(row) > 9 and row[9].value:
                            person = str(row[9].value).strip()

                        notes = ''
                        if len(row) > 10 and row[10].value:
                            notes = str(row[10].value).strip()

                        # Use the first available date from the week
                        week_ref_date = next((d for d in week_dates if d), None)
                        todos.append({
                            'title': todo_text,
                            'is_completed': is_completed,
                            'responsible_person': person,
                            'notes': notes,
                            'due_date': week_ref_date,
                        })

    wb.close()
    return schedules, todos
