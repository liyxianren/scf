import os

import pytest
from freezegun import freeze_time

os.environ.setdefault('SCF_SKIP_APP_AUTO_CREATE', '1')

from app import create_app
from config import TestingConfig
from extensions import db


@pytest.fixture
def frozen_time():
    with freeze_time('2026-03-16 09:00:00+08:00'):
        yield


@pytest.fixture
def app(tmp_path, frozen_time):
    db_path = tmp_path / 'test.db'
    storage_root = tmp_path / 'handbooks'
    storage_root.mkdir(parents=True, exist_ok=True)

    app = create_app(
        TestingConfig,
        config_overrides={
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path.as_posix()}',
            'HANDBOOK_STORAGE_ROOT': str(storage_root),
        },
    )

    ctx = app.app_context()
    ctx.push()
    try:
        yield app
    finally:
        db.session.remove()
        db.drop_all()
        ctx.pop()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_session(app):
    return db.session


@pytest.fixture
def login_as(client):
    def _login(user_or_username, password='scf123', follow_redirects=False):
        username = getattr(user_or_username, 'username', user_or_username)
        return client.post(
            '/auth/login',
            data={'username': username, 'password': password},
            follow_redirects=follow_redirects,
        )

    return _login


@pytest.fixture
def logout(client):
    def _logout():
        return client.get('/auth/logout', follow_redirects=False)

    return _logout
