import importlib
import sys
from flask import Flask


def reload_config_module(monkeypatch, **env):
    for key in ['SCF_DATABASE_URL', 'DATABASE_URL', 'SCF_DB_PATH', 'SCF_RUNTIME_ROOT']:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    sys.modules.pop('config', None)
    import config
    return importlib.reload(config)


def test_config_prefers_explicit_database_url(monkeypatch):
    config = reload_config_module(
        monkeypatch,
        SCF_DATABASE_URL='mysql+pymysql://scf_user:secret@127.0.0.1:3306/scf_prod?charset=utf8mb4',
        SCF_DB_PATH='/tmp/should_not_be_used.db',
    )

    assert config.Config.SQLALCHEMY_DATABASE_URI == (
        'mysql+pymysql://scf_user:secret@127.0.0.1:3306/scf_prod?charset=utf8mb4'
    )


def test_schedule_import_root_prefers_runtime_root_for_non_sqlite(tmp_path):
    from modules.oa import services

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://scf_user:secret@127.0.0.1:3306/scf_prod'
    app.config['SCF_RUNTIME_ROOT'] = tmp_path.as_posix()

    with app.app_context():
        root = services.get_schedule_import_root()

    assert root == str(tmp_path / 'imports' / 'schedules')
