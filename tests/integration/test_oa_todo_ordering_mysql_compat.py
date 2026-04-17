"""Regression: OA todo / workflow ordering must be MySQL-safe.

Root cause: SQLAlchemy's ``Column.nullslast()`` emits ``ORDER BY ... NULLS LAST``
which MySQL rejects with ``pymysql.err.ProgrammingError (1064)``. Production
``/oa/todos`` showed ``加载失败`` on shared MySQL because this clause was used
in ``modules/oa/routes.py``, ``modules/oa/external_routes.py``, and
``modules/auth/workflow_services.py``.
"""
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import mysql

from modules.oa.models import OATodo
from tests.factories import create_todo, create_user


pytestmark = pytest.mark.integration


_REPO_ROOT = Path(__file__).resolve().parents[2]
_ORDERING_CALL_SITES = (
    _REPO_ROOT / 'modules' / 'oa' / 'routes.py',
    _REPO_ROOT / 'modules' / 'oa' / 'external_routes.py',
    _REPO_ROOT / 'modules' / 'auth' / 'workflow_services.py',
)


def _compiled_mysql(stmt):
    return str(stmt.compile(dialect=mysql.dialect()))


def test_oa_todo_list_ordering_compiles_without_nulls_last_for_mysql(app):
    # Mirrors order_by() in api_list_todos / external_list_todos.
    stmt = select(OATodo).order_by(
        OATodo.is_completed,
        OATodo.priority,
        OATodo.due_date.is_(None).asc(),
        OATodo.due_date.asc(),
    )
    sql = _compiled_mysql(stmt).upper()
    assert 'NULLS LAST' not in sql, sql
    assert 'NULLS FIRST' not in sql, sql


def test_workflow_todo_list_ordering_compiles_without_nulls_last_for_mysql(app):
    # Mirrors order_by() in list_workflow_todos_for_user.
    stmt = select(OATodo).order_by(
        OATodo.is_completed,
        OATodo.priority,
        OATodo.due_date.is_(None).asc(),
        OATodo.due_date.asc(),
        OATodo.created_at.desc(),
    )
    sql = _compiled_mysql(stmt).upper()
    assert 'NULLS LAST' not in sql, sql


def test_no_nullslast_in_oa_todo_ordering_source_sites():
    """Static guard: none of the three call sites re-introduce ``.nullslast()``.

    The production bug appears when ``OATodo.due_date.asc().nullslast()``
    (or any other ``.nullslast()`` call on an OATodo column) is compiled
    against MySQL, so we forbid the emitter at the source level.
    """
    offenders = []
    for path in _ORDERING_CALL_SITES:
        text = path.read_text(encoding='utf-8')
        if '.nullslast(' in text:
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert not offenders, (
        'Found .nullslast() ordering in files that are queried on MySQL: '
        f'{offenders}. Use a portable ordering like '
        '`col.is_(None).asc(), col.asc()` instead.'
    )


def test_oa_todo_list_endpoint_orders_null_due_dates_last(app, client, login_as, monkeypatch):
    # Local Python builds without ``hashlib.scrypt`` (e.g. python 3.9 + LibreSSL
    # on macOS) can't hash passwords via werkzeug's default scrypt method. Force
    # pbkdf2 for this test so the admin-login fixture works; this is a purely
    # local environment workaround and does not affect production hashing.
    from werkzeug.security import generate_password_hash as _real_generate_password_hash
    from modules.auth import models as auth_models

    def _pbkdf2_generate_password_hash(password, method='pbkdf2:sha256', salt_length=16):
        return _real_generate_password_hash(password, method='pbkdf2:sha256', salt_length=salt_length)

    monkeypatch.setattr(auth_models, 'generate_password_hash', _pbkdf2_generate_password_hash)

    admin = create_user(username='oa-admin-ordering', display_name='排序管理员', role='admin')
    login_as(admin)

    with_early = create_todo(title='有截止日期-早', due_date=date(2026, 3, 1), priority=2)
    with_late = create_todo(title='有截止日期-晚', due_date=date(2026, 4, 1), priority=2)
    without_date = create_todo(title='无截止日期', due_date=None, priority=2)

    response = client.get('/oa/api/todos?status=pending')
    assert response.status_code == 200, response.data
    payload = response.get_json()
    assert payload['success'] is True
    titles = [item['title'] for item in payload['data']]
    assert with_early.title in titles
    assert with_late.title in titles
    assert without_date.title in titles
    assert titles.index(with_early.title) < titles.index(without_date.title)
    assert titles.index(with_late.title) < titles.index(without_date.title)
