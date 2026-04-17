import pytest

from config import TestingConfig
from extensions import db


pytestmark = pytest.mark.integration


def _rules(app):
    return {rule.rule for rule in app.url_map.iter_rules()}


def _teardown(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_public_factory_registers_public_and_oa(tmp_path):
    from app_factory import create_app

    app = create_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "public.db").as_posix()}',
        },
    )
    try:
        rules = _rules(app)
        assert any(r.startswith('/oa/') for r in rules), 'public app should mount /oa'
        assert any(r.startswith('/auth/') for r in rules), 'public app should mount /auth'
        assert any(r.startswith('/api/lessons') for r in rules), 'public app should mount education API'
        assert '/' in rules, 'public app should expose landing page'
        assert '/python/lessons' in rules, 'public app should expose legacy public pages'
    finally:
        _teardown(app)


def test_oa_factory_registers_oa_without_public_surface(tmp_path):
    from app_factory import create_oa_app

    app = create_oa_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "oa.db").as_posix()}',
        },
    )
    try:
        rules = _rules(app)
        assert any(r.startswith('/oa/') for r in rules), 'oa app must mount /oa'
        assert any(r.startswith('/auth/') for r in rules), 'oa app must still share /auth'
        assert not any(r.startswith('/api/lessons') for r in rules), 'oa app should not carry education API'
        assert not any(r.startswith('/python/') for r in rules), 'oa app should not carry public teaching pages'
        assert not any(r.startswith('/company/') for r in rules), 'oa app should not carry agent/handbook surface'
        assert '/' not in rules, 'oa app should not own the landing page'
    finally:
        _teardown(app)


def test_app_module_preserves_create_app_import(tmp_path):
    from app import create_app

    app = create_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "legacy.db").as_posix()}',
        },
    )
    try:
        rules = _rules(app)
        assert any(r.startswith('/oa/') for r in rules)
        assert any(r.startswith('/api/lessons') for r in rules)
        assert '/' in rules
    finally:
        _teardown(app)


def test_oa_app_module_exposes_entrypoint(tmp_path):
    import oa_app

    assert callable(getattr(oa_app, 'create_oa_app', None)), 'oa_app must expose create_oa_app'

    app = oa_app.create_oa_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "oa_entry.db").as_posix()}',
        },
    )
    try:
        rules = _rules(app)
        assert any(r.startswith('/oa/') for r in rules)
        assert not any(r.startswith('/api/lessons') for r in rules)
    finally:
        _teardown(app)


def test_oa_factory_auth_login_renders_through_oa_shell(tmp_path):
    from app_factory import create_oa_app

    app = create_oa_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "oa_auth_shell.db").as_posix()}',
        },
    )
    try:
        client = app.test_client()
        response = client.get('/auth/login')
        assert response.status_code == 200, 'oa /auth/login must render'
        body = response.get_data(as_text=True)

        assert 'data-oa-shell="1"' in body, 'oa /auth/login must render through the OA shell'

        assert 'href="/summer"' not in body, 'oa /auth/login must not leak /summer link'
        assert 'href="/code"' not in body, 'oa /auth/login must not leak /code link'
        assert 'class="nav-logo">\n                    <img' not in body, (
            'oa /auth/login must not render the public two-tier navbar'
        )
    finally:
        _teardown(app)


def test_public_factory_auth_login_keeps_public_shell(tmp_path):
    from app_factory import create_app

    app = create_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "public_auth_shell.db").as_posix()}',
        },
    )
    try:
        client = app.test_client()
        response = client.get('/auth/login')
        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert 'data-oa-shell="1"' not in body, 'public /auth/login should keep the public shell'
        assert 'href="/summer"' in body, 'public /auth/login should still show public nav'
        assert 'href="/code"' in body, 'public /auth/login should still show public nav'
    finally:
        _teardown(app)


def test_oa_factory_skips_seed_init_by_default_even_if_config_requests_it(tmp_path, monkeypatch):
    import app_factory

    def fail_hook(name):
        def _raise():
            raise AssertionError(f'create_oa_app should not run {name} by default')
        return _raise

    monkeypatch.setattr(app_factory, '_init_data', fail_hook('_init_data'))
    monkeypatch.setattr(app_factory, '_backfill_schedule_links', fail_hook('_backfill_schedule_links'))
    monkeypatch.setattr(app_factory, '_cleanup_expired', fail_hook('_cleanup_expired'))
    monkeypatch.setattr(app_factory, '_run_startup_hooks', app_factory._run_startup_hooks)

    app = app_factory.create_oa_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "oa_default_init.db").as_posix()}',
            'SCF_AUTO_INIT_DATA': True,
            'SCF_AUTO_BACKFILL_SCHEDULE_LINKS': True,
            'SCF_AUTO_CLEANUP_EXPIRED': True,
            'SCF_RUN_ONCE_MIGRATIONS': True,
        },
    )
    try:
        assert app is not None
    finally:
        _teardown(app)
