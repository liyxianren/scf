from unittest.mock import Mock

import migrations_once


def test_migration_table_uses_mysql_safe_primary_key(monkeypatch):
    execute = Mock()
    commit = Mock()
    monkeypatch.setattr(migrations_once.db, 'session', Mock(execute=execute, commit=commit))

    migrations_once._ensure_migration_table()

    sql = str(execute.call_args[0][0])
    assert 'name VARCHAR(255) PRIMARY KEY' in sql
    assert 'name TEXT PRIMARY KEY' not in sql
