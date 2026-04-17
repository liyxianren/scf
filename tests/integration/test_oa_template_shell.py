"""Verify OA page templates render through a dedicated OA shell."""
import pytest
from flask import render_template

from config import TestingConfig
from extensions import db


pytestmark = pytest.mark.integration


OA_PAGE_TEMPLATES = [
    'oa/dashboard.html',
    'oa/schedule.html',
    'oa/todos.html',
    'oa/painpoints.html',
]

OA_SHELL_MARKER = 'data-oa-shell'
PUBLIC_SHELL_FOOTER = 'SCF Code Learn - 熵创未来教育科技'
PUBLIC_SHELL_LANG_SCRIPT = 'window.CURRENT_LANGUAGE'
PUBLIC_SHELL_ASSET = 'cloudflare.com/ajax/libs/codemirror'


def _teardown(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def oa_app(tmp_path):
    from app_factory import create_oa_app

    app = create_oa_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "oa_shell.db").as_posix()}',
        },
    )
    try:
        yield app
    finally:
        _teardown(app)


def _render(app, template_name):
    context = {}
    if template_name == 'oa/todos.html':
        context['staff_options'] = []
    with app.test_request_context('/oa/'):
        return render_template(template_name, **context)


def test_oa_base_template_exists(oa_app):
    rendered = _render(oa_app, 'oa/base.html')
    assert OA_SHELL_MARKER in rendered, 'oa/base.html must tag itself as the OA shell'


@pytest.mark.parametrize('template_name', OA_PAGE_TEMPLATES)
def test_oa_template_uses_oa_shell(oa_app, template_name):
    html = _render(oa_app, template_name)
    assert OA_SHELL_MARKER in html, (
        f'{template_name} should render through oa/base.html (missing {OA_SHELL_MARKER})'
    )


@pytest.mark.parametrize('template_name', OA_PAGE_TEMPLATES)
def test_oa_template_does_not_inherit_public_shell(oa_app, template_name):
    html = _render(oa_app, template_name)
    assert PUBLIC_SHELL_FOOTER not in html, (
        f'{template_name} still renders the public-site footer branding'
    )
    assert PUBLIC_SHELL_LANG_SCRIPT not in html, (
        f'{template_name} still loads the public-site language script'
    )
    assert PUBLIC_SHELL_ASSET not in html, (
        f'{template_name} still loads public-site CodeMirror assets'
    )
