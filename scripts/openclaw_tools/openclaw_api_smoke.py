"""Canonical smoke client for OpenClaw integration APIs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = 'http://127.0.0.1:5000'
DEFAULT_TOKEN = 'openclaw233'
DEFAULT_PROVIDER = 'feishu'


def _request_json(
    *,
    method: str,
    base_url: str,
    token: str,
    path: str,
    query: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        query_string = urlencode({key: value for key, value in query.items() if value is not None})
        if query_string:
            url = f'{url}?{query_string}'

    body = None
    headers = {
        'X-Integration-Token': token,
        'Accept': 'application/json',
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    request = Request(url, method=method.upper(), headers=headers, data=body)
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {'success': False, 'error': body or str(exc)}
        payload.setdefault('http_status', exc.code)
        return payload
    except URLError as exc:
        return {
            'success': False,
            'error': f'network_error: {exc}',
        }


class OpenClawClient:
    def __init__(self, *, base_url: str, token: str, provider: str, external_user_id: str) -> None:
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.provider = provider
        self.external_user_id = external_user_id

    def _identity_query(self, **extra: Any) -> dict[str, Any]:
        query = {
            'provider': self.provider,
            'external_user_id': self.external_user_id,
        }
        query.update({key: value for key, value in extra.items() if value is not None})
        return query

    def summary(self) -> dict[str, Any]:
        return _request_json(
            method='GET',
            base_url=self.base_url,
            token=self.token,
            path='/oa/api/integration/openclaw/me/summary',
            query=self._identity_query(),
        )

    def schedules(self, *, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        return _request_json(
            method='GET',
            base_url=self.base_url,
            token=self.token,
            path='/oa/api/integration/openclaw/me/schedules',
            query=self._identity_query(start=start, end=end),
        )

    def work_items(self) -> dict[str, Any]:
        return _request_json(
            method='GET',
            base_url=self.base_url,
            token=self.token,
            path='/oa/api/integration/openclaw/me/work-items',
            query=self._identity_query(),
        )

    def reminders(self, *, status: str = 'pending', limit: int = 20, cursor: int | None = None) -> dict[str, Any]:
        return _request_json(
            method='GET',
            base_url=self.base_url,
            token=self.token,
            path='/oa/api/integration/openclaw/reminders',
            query=self._identity_query(status=status, limit=limit, cursor=cursor),
        )

    def ack(self, *, event_ids: list[int], request_id: str | None = None) -> dict[str, Any]:
        return _request_json(
            method='POST',
            base_url=self.base_url,
            token=self.token,
            path='/oa/api/integration/openclaw/reminders/ack',
            payload={
                'provider': self.provider,
                'external_user_id': self.external_user_id,
                'request_id': request_id or f"smoke-ack-{int(datetime.utcnow().timestamp() * 1000)}",
                'event_ids': event_ids,
            },
        )


def _ensure_success(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get('success'):
        raise RuntimeError(
            f"{name} failed: {json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
    return payload.get('data') or {}


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _format_schedule_line(item: dict[str, Any]) -> str:
    return (
        f"- {item.get('date')} {item.get('time_start')}-{item.get('time_end')} | "
        f"{item.get('course_name') or 'Untitled'} | "
        f"学生: {item.get('students') or item.get('student_name') or '-'} | "
        f"老师: {item.get('teacher') or item.get('teacher_name') or '-'}"
    )


def _format_todo_line(item: dict[str, Any]) -> str:
    title = item.get('title') or item.get('todo_type_label') or item.get('event_type') or 'Todo'
    summary = item.get('context_summary') or item.get('summary') or item.get('student_name') or ''
    return f"- {title}" + (f" | {summary}" if summary else '')


def _today_str(explicit_date: str | None) -> str:
    return explicit_date or date.today().isoformat()


def _render_daily_brief(
    *,
    target_date: str,
    summary: dict[str, Any],
    schedules: dict[str, Any],
    work_items: dict[str, Any],
    reminders: dict[str, Any],
) -> str:
    actor = summary.get('actor') or {}
    counts = summary.get('counts') or {}
    schedule_items = schedules.get('items') or []
    workflow_items = work_items.get('workflow_todos') or []
    feedback_items = work_items.get('pending_feedback_schedules') or []
    leave_items = work_items.get('pending_leave_requests') or []
    reminder_items = reminders.get('items') or []

    lines = [
        f"OpenClaw daily brief for {actor.get('display_name') or actor.get('username') or 'unknown'}",
        f"Role: {actor.get('role') or 'unknown'}",
        f"Date: {target_date}",
        (
            "Counts: "
            f"workflow={counts.get('proposal_workflows', counts.get('pending_admin_send_workflows', 0))}, "
            f"feedback={counts.get('pending_feedback_schedules', 0)}, "
            f"leave={counts.get('pending_leave_requests', 0)}, "
            f"today_classes={len(schedule_items)}, "
            f"pending_reminders={len(reminder_items)}"
        ),
        '',
        'Today schedules',
    ]
    lines.extend(_format_schedule_line(item) for item in schedule_items) if schedule_items else lines.append('- none')
    lines.extend(['', 'Workflow todos'])
    lines.extend(_format_todo_line(item) for item in workflow_items[:8]) if workflow_items else lines.append('- none')
    lines.extend(['', 'Pending feedback'])
    lines.extend(_format_schedule_line(item) for item in feedback_items[:8]) if feedback_items else lines.append('- none')
    lines.extend(['', 'Pending leave'])
    lines.extend(_format_todo_line(item) for item in leave_items[:8]) if leave_items else lines.append('- none')
    lines.extend(['', 'Pending reminders'])
    lines.extend(_format_todo_line(item) for item in reminder_items[:10]) if reminder_items else lines.append('- none')
    return '\n'.join(lines)


def command_summary(args: argparse.Namespace) -> int:
    client = OpenClawClient(
        base_url=args.base_url,
        token=args.token,
        provider=args.provider,
        external_user_id=args.external_user_id,
    )
    response = client.summary()
    if args.json:
        _print_json(response)
        return 0 if response.get('success') else 1
    payload = _ensure_success('summary', response)
    actor = payload.get('actor') or {}
    print(f"Actor: {actor.get('display_name') or actor.get('username') or args.external_user_id}")
    print(f"Role: {actor.get('role') or '-'}")
    print(f"Primary action: {payload.get('primary_action') or '-'}")
    print(json.dumps(payload.get('counts') or {}, ensure_ascii=False, indent=2))
    return 0


def command_schedule(args: argparse.Namespace) -> int:
    client = OpenClawClient(
        base_url=args.base_url,
        token=args.token,
        provider=args.provider,
        external_user_id=args.external_user_id,
    )
    target_date = _today_str(args.date)
    start = args.start or target_date
    end = args.end or target_date
    response = client.schedules(start=start, end=end)
    if args.json:
        _print_json(response)
        return 0 if response.get('success') else 1
    payload = _ensure_success('schedules', response)
    items = payload.get('items') or []
    print(f"Schedule results: {payload.get('total', len(items))}")
    for item in items:
        print(_format_schedule_line(item))
    if not items:
        print('- none')
    return 0


def command_work_items(args: argparse.Namespace) -> int:
    client = OpenClawClient(
        base_url=args.base_url,
        token=args.token,
        provider=args.provider,
        external_user_id=args.external_user_id,
    )
    response = client.work_items()
    if args.json:
        _print_json(response)
        return 0 if response.get('success') else 1
    payload = _ensure_success('work-items', response)
    print(json.dumps(payload.get('counts') or {}, ensure_ascii=False, indent=2))
    return 0


def command_reminders(args: argparse.Namespace) -> int:
    client = OpenClawClient(
        base_url=args.base_url,
        token=args.token,
        provider=args.provider,
        external_user_id=args.external_user_id,
    )
    response = client.reminders(status=args.status, limit=args.limit, cursor=args.cursor)
    if args.json:
        _print_json(response)
        return 0 if response.get('success') else 1
    payload = _ensure_success('reminders', response)
    print(f"Reminder status: {payload.get('status')}")
    print(f"Total: {payload.get('total')}")
    for item in payload.get('items') or []:
        print(_format_todo_line(item))
    if not (payload.get('items') or []):
        print('- none')
    return 0


def command_ack(args: argparse.Namespace) -> int:
    client = OpenClawClient(
        base_url=args.base_url,
        token=args.token,
        provider=args.provider,
        external_user_id=args.external_user_id,
    )
    response = client.ack(event_ids=args.event_ids, request_id=args.request_id)
    if args.json:
        _print_json(response)
        return 0 if response.get('success') else 1
    payload = _ensure_success('ack', response)
    print(f"Acked count: {payload.get('acked_count', 0)}")
    print(f"Acked event ids: {payload.get('acked_event_ids') or []}")
    return 0


def command_daily_brief(args: argparse.Namespace) -> int:
    client = OpenClawClient(
        base_url=args.base_url,
        token=args.token,
        provider=args.provider,
        external_user_id=args.external_user_id,
    )
    target_date = _today_str(args.date)
    summary = client.summary()
    schedules = client.schedules(start=target_date, end=target_date)
    work_items = client.work_items()
    reminders = client.reminders(status='pending', limit=args.limit)
    bundle = {
        'date': target_date,
        'summary': summary,
        'today_schedules': schedules,
        'work_items': work_items,
        'pending_reminders': reminders,
    }
    if args.json:
        _print_json(bundle)
        return 0 if all(item.get('success') for item in bundle.values() if isinstance(item, dict)) else 1

    summary_payload = _ensure_success('summary', summary)
    schedule_payload = _ensure_success('schedules', schedules)
    work_items_payload = _ensure_success('work-items', work_items)
    reminder_payload = _ensure_success('reminders', reminders)
    print(_render_daily_brief(
        target_date=target_date,
        summary=summary_payload,
        schedules=schedule_payload,
        work_items=work_items_payload,
        reminders=reminder_payload,
    ))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Canonical OpenClaw integration smoke client.')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL)
    parser.add_argument('--token', default=DEFAULT_TOKEN)
    parser.add_argument('--provider', default=DEFAULT_PROVIDER)
    parser.add_argument('--external-user-id', required=True)
    parser.add_argument('--json', action='store_true', help='Print raw JSON payloads.')

    subparsers = parser.add_subparsers(dest='command', required=True)

    summary_parser = subparsers.add_parser('summary', help='Fetch me/summary.')
    summary_parser.set_defaults(func=command_summary)

    schedule_parser = subparsers.add_parser('schedule-query', help='Fetch actor-scoped schedules.')
    schedule_parser.add_argument('--date')
    schedule_parser.add_argument('--start')
    schedule_parser.add_argument('--end')
    schedule_parser.set_defaults(func=command_schedule)

    schedule_alias = subparsers.add_parser('schedule', help='Alias of schedule-query.')
    schedule_alias.add_argument('--date')
    schedule_alias.add_argument('--start')
    schedule_alias.add_argument('--end')
    schedule_alias.set_defaults(func=command_schedule)

    work_items_parser = subparsers.add_parser('work-items', help='Fetch me/work-items.')
    work_items_parser.set_defaults(func=command_work_items)

    reminders_parser = subparsers.add_parser('reminders', help='Fetch reminders feed.')
    reminders_parser.add_argument('--status', default='pending', choices=['pending', 'acked'])
    reminders_parser.add_argument('--limit', type=int, default=20)
    reminders_parser.add_argument('--cursor', type=int)
    reminders_parser.set_defaults(func=command_reminders)

    ack_parser = subparsers.add_parser('ack', help='Ack reminder event ids.')
    ack_parser.add_argument('--event-id', dest='event_ids', action='append', type=int, required=True)
    ack_parser.add_argument('--request-id')
    ack_parser.set_defaults(func=command_ack)

    daily_parser = subparsers.add_parser('daily-brief', help='Fetch summary + today schedules + work-items + reminders.')
    daily_parser.add_argument('--date')
    daily_parser.add_argument('--limit', type=int, default=10)
    daily_parser.set_defaults(func=command_daily_brief)

    daily_alias = subparsers.add_parser('daily-digest', help='Alias of daily-brief.')
    daily_alias.add_argument('--date')
    daily_alias.add_argument('--limit', type=int, default=10)
    daily_alias.set_defaults(func=command_daily_brief)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
