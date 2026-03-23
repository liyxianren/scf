"""Manage ExternalIdentity bindings for OpenClaw / Feishu actors."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from pathlib import Path

from sqlalchemy import or_


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from app import create_app
from config import Config
from extensions import db
from modules.auth.models import ExternalIdentity, User


def _build_app():
    return create_app(
        Config,
        migrate_columns=True,
        init_data=False,
        backfill_schedule_links=False,
        cleanup_expired=False,
        run_once_migrations=False,
    )


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _resolve_user(*, username: str | None, user_id: int | None) -> User:
    user = None
    if user_id is not None:
        user = db.session.get(User, user_id)
    elif username:
        user = User.query.filter_by(username=username).first()
    if not user:
        lookup = f'user_id={user_id}' if user_id is not None else f'username={username}'
        raise RuntimeError(f'User not found: {lookup}')
    return user


def _resolve_binding(provider: str, external_user_id: str) -> ExternalIdentity | None:
    return ExternalIdentity.query.filter_by(
        provider=(provider or '').strip().lower(),
        external_user_id=(external_user_id or '').strip(),
    ).first()


def _binding_payload(binding: ExternalIdentity) -> dict[str, Any]:
    payload = binding.to_dict()
    payload['user'] = binding.user.to_dict() if binding.user else None
    return payload


def command_list_users(args: argparse.Namespace) -> int:
    query = User.query
    if args.role:
        query = query.filter_by(role=args.role)
    if args.active_only:
        query = query.filter_by(is_active=True)
    if args.query:
        like = f"%{args.query}%"
        query = query.filter(
            or_(User.username.ilike(like), User.display_name.ilike(like))
        )
    users = query.order_by(User.role, User.username).all()
    payload = [user.to_dict() for user in users]
    if args.json:
        _print_json(payload)
    else:
        for user in payload:
            print(
                f"{user['id']:>3} | {user['role']:<7} | {user['username']:<20} | "
                f"{user['display_name']:<20} | active={user['is_active']}"
            )
    return 0


def command_list_bindings(args: argparse.Namespace) -> int:
    query = ExternalIdentity.query
    if args.provider:
        query = query.filter_by(provider=args.provider.strip().lower())
    if args.status:
        query = query.filter_by(status=args.status)
    if args.external_user_id:
        query = query.filter_by(external_user_id=args.external_user_id.strip())
    if args.username:
        user = _resolve_user(username=args.username, user_id=None)
        query = query.filter_by(user_id=user.id)
    bindings = query.order_by(ExternalIdentity.provider, ExternalIdentity.external_user_id).all()
    payload = [_binding_payload(binding) for binding in bindings]
    if args.json:
        _print_json(payload)
    else:
        for item in payload:
            user = item.get('user') or {}
            print(
                f"{item['provider']:<8} | {item['external_user_id']:<30} | "
                f"{item['status']:<8} | {user.get('username', '-'):<20} | {user.get('role', '-')}"
            )
    return 0


def command_whois(args: argparse.Namespace) -> int:
    binding = _resolve_binding(args.provider, args.external_user_id)
    if not binding:
        raise RuntimeError('Binding not found')
    payload = _binding_payload(binding)
    if args.json:
        _print_json(payload)
    else:
        user = payload.get('user') or {}
        print(f"provider={payload['provider']}")
        print(f"external_user_id={payload['external_user_id']}")
        print(f"status={payload['status']}")
        print(f"user={user.get('username')} ({user.get('display_name')}) role={user.get('role')}")
    return 0


def _bind_user(*, provider: str, external_user_id: str, user: User, allow_rebind: bool, status: str) -> ExternalIdentity:
    binding = _resolve_binding(provider, external_user_id)
    if binding:
        if binding.user_id != user.id and not allow_rebind:
            raise RuntimeError(
                f'Binding already exists for {provider}:{external_user_id}. '
                'Use switch or --allow-rebind to replace it.'
            )
        binding.user_id = user.id
        binding.status = status
        db.session.commit()
        return binding

    binding = ExternalIdentity(
        provider=provider,
        external_user_id=external_user_id,
        user_id=user.id,
        status=status,
    )
    db.session.add(binding)
    db.session.commit()
    return binding


def command_bind(args: argparse.Namespace) -> int:
    user = _resolve_user(username=args.username, user_id=args.user_id)
    binding = _bind_user(
        provider=args.provider.strip().lower(),
        external_user_id=args.external_user_id.strip(),
        user=user,
        allow_rebind=args.allow_rebind,
        status=args.status,
    )
    payload = _binding_payload(binding)
    if args.json:
        _print_json(payload)
    else:
        print(
            f"Bound {payload['provider']}:{payload['external_user_id']} -> "
            f"{payload['user']['username']} ({payload['user']['role']}) status={payload['status']}"
        )
    return 0


def command_switch(args: argparse.Namespace) -> int:
    binding = _resolve_binding(args.provider, args.external_user_id)
    if not binding:
        raise RuntimeError('Binding not found. Use bind first.')
    user = _resolve_user(username=args.username, user_id=args.user_id)
    binding = _bind_user(
        provider=args.provider.strip().lower(),
        external_user_id=args.external_user_id.strip(),
        user=user,
        allow_rebind=True,
        status=args.status,
    )
    payload = _binding_payload(binding)
    if args.json:
        _print_json(payload)
    else:
        print(
            f"Switched {payload['provider']}:{payload['external_user_id']} -> "
            f"{payload['user']['username']} ({payload['user']['role']}) status={payload['status']}"
        )
    return 0


def command_set_status(args: argparse.Namespace) -> int:
    binding = _resolve_binding(args.provider, args.external_user_id)
    if not binding:
        raise RuntimeError('Binding not found')
    binding.status = args.status
    db.session.commit()
    payload = _binding_payload(binding)
    if args.json:
        _print_json(payload)
    else:
        print(f"Updated {payload['provider']}:{payload['external_user_id']} status -> {payload['status']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Manage provider + external_user_id -> User bindings.',
    )
    parser.add_argument('--json', action='store_true', help='Print JSON output.')

    subparsers = parser.add_subparsers(dest='command', required=True)

    list_users = subparsers.add_parser('list-users', help='List website users.')
    list_users.add_argument('--role', choices=['admin', 'teacher', 'student'])
    list_users.add_argument('--query')
    list_users.add_argument('--active-only', action='store_true')
    list_users.set_defaults(func=command_list_users)

    list_bindings = subparsers.add_parser('list-bindings', help='List ExternalIdentity bindings.')
    list_bindings.add_argument('--provider', default='feishu')
    list_bindings.add_argument('--status')
    list_bindings.add_argument('--external-user-id')
    list_bindings.add_argument('--username')
    list_bindings.set_defaults(func=command_list_bindings)

    whois = subparsers.add_parser('whois', help='Show a binding target.')
    whois.add_argument('--provider', default='feishu')
    whois.add_argument('--external-user-id', required=True)
    whois.set_defaults(func=command_whois)

    bind = subparsers.add_parser('bind', help='Create or update a binding.')
    bind.add_argument('--provider', default='feishu')
    bind.add_argument('--external-user-id', required=True)
    bind.add_argument('--username')
    bind.add_argument('--user-id', type=int)
    bind.add_argument('--status', default='active', choices=['active', 'inactive'])
    bind.add_argument('--allow-rebind', action='store_true')
    bind.set_defaults(func=command_bind)

    switch = subparsers.add_parser('switch', help='Rebind an existing external identity to another user.')
    switch.add_argument('--provider', default='feishu')
    switch.add_argument('--external-user-id', required=True)
    switch.add_argument('--username')
    switch.add_argument('--user-id', type=int)
    switch.add_argument('--status', default='active', choices=['active', 'inactive'])
    switch.set_defaults(func=command_switch)

    activate = subparsers.add_parser('activate', help='Set a binding to active.')
    activate.add_argument('--provider', default='feishu')
    activate.add_argument('--external-user-id', required=True)
    activate.set_defaults(func=command_set_status, status='active')

    deactivate = subparsers.add_parser('deactivate', help='Set a binding to inactive.')
    deactivate.add_argument('--provider', default='feishu')
    deactivate.add_argument('--external-user-id', required=True)
    deactivate.set_defaults(func=command_set_status, status='inactive')

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = _build_app()
    with app.app_context():
        return args.func(args)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
