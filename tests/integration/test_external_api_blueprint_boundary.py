"""Blueprint ownership boundaries for external OA API routes.

Auth-domain external APIs (teacher availability, enrollments, student profiles,
leave requests) live on the auth blueprint. OA-owned external APIs
(dashboard stats, schedules, todos, import-excel) remain on the OA blueprint.
"""
import pytest

from config import TestingConfig
from extensions import db


pytestmark = pytest.mark.integration


AUTH_DOMAIN_EXTERNAL_PATHS = [
    '/auth/api/external/teachers/<int:teacher_id>/availability',
    '/auth/api/external/enrollments',
    '/auth/api/external/enrollments/create',
    '/auth/api/external/enrollments/<int:enrollment_id>',
    '/auth/api/external/enrollments/<int:enrollment_id>/intake-submit',
    '/auth/api/external/enrollments/<int:enrollment_id>/match',
    '/auth/api/external/enrollments/<int:enrollment_id>/confirm-slot',
    '/auth/api/external/enrollments/<int:enrollment_id>/confirm',
    '/auth/api/external/enrollments/<int:enrollment_id>/student-confirm',
    '/auth/api/external/enrollments/<int:enrollment_id>/student-reject',
    '/auth/api/external/enrollments/<int:enrollment_id>/export',
    '/auth/api/external/enrollments/progress',
    '/auth/api/external/student-profiles',
    '/auth/api/external/student-profiles/<int:profile_id>',
    '/auth/api/external/leave-requests',
    '/auth/api/external/leave-requests/<int:request_id>/approve',
    '/auth/api/external/leave-requests/<int:request_id>/reject',
]


OA_DOMAIN_EXTERNAL_PATHS = [
    '/oa/api/external/dashboard-stats',
    '/oa/api/external/schedules',
    '/oa/api/external/schedules/date-range',
    '/oa/api/external/schedules/by-date',
    '/oa/api/external/schedules/<int:schedule_id>',
    '/oa/api/external/schedules/teachers',
    '/oa/api/external/schedules/students',
    '/oa/api/external/schedules/progress',
    '/oa/api/external/todos',
    '/oa/api/external/todos/<int:todo_id>',
    '/oa/api/external/todos/<int:todo_id>/toggle',
    '/oa/api/external/todos/batch',
    '/oa/api/external/import-excel',
]


AUTH_OWNED_SUFFIXES_FORBIDDEN_ON_OA = [
    '/oa/api/external/teachers/',
    '/oa/api/external/enrollments',
    '/oa/api/external/student-profiles',
    '/oa/api/external/leave-requests',
]


def _rules(app):
    return {rule.rule for rule in app.url_map.iter_rules()}


def _teardown(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def app(tmp_path):
    from app_factory import create_app

    app = create_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "boundary.db").as_posix()}',
        },
    )
    try:
        yield app
    finally:
        _teardown(app)


def test_auth_domain_external_routes_mount_under_auth(app):
    rules = _rules(app)
    missing = [path for path in AUTH_DOMAIN_EXTERNAL_PATHS if path not in rules]
    assert not missing, (
        'auth-domain external routes should mount under /auth/api/external/...; '
        f'missing: {missing}'
    )


def test_auth_domain_external_routes_not_under_oa(app):
    rules = _rules(app)
    leaked = [
        rule
        for rule in rules
        if any(rule.startswith(prefix) for prefix in AUTH_OWNED_SUFFIXES_FORBIDDEN_ON_OA)
    ]
    assert not leaked, (
        'auth-domain external routes must not remain under /oa/api/external/...; '
        f'leaked: {leaked}'
    )


def test_oa_owned_external_routes_remain_under_oa(app):
    rules = _rules(app)
    missing = [path for path in OA_DOMAIN_EXTERNAL_PATHS if path not in rules]
    assert not missing, (
        'OA-owned external routes should remain under /oa/api/external/...; '
        f'missing: {missing}'
    )
