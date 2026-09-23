import pytest
from app import core

@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / 'tasks.db')
    core.init_db(path)
    return path

@pytest.mark.parametrize('payload', [{}, {'title': ''}, {'title': ' '*4}, {'title': 7}, {'title': 'x'*121}, None])
def test_bad_title(db, payload):
    with pytest.raises(ValueError):
        core.add_task(payload, db)

def test_crud(db):
    assert core.list_tasks(db) == []
    item = core.add_task({'title': '  Test CI/CD  '}, db)
    assert item['title'] == 'Test CI/CD' and not item['done']
    assert len(core.list_tasks(db)) == 1
    assert core.update_task(item['id'], {'done': True}, db)['done'] is True
    assert core.delete_task(item['id'], db)
    assert core.list_tasks(db) == []
    assert not core.delete_task(item['id'], db)

def test_boolean_validation(db):
    item = core.add_task({'title': 'A'}, db)
    with pytest.raises(ValueError):
        core.update_task(item['id'], {'done': 1}, db)

def test_not_found(db):
    assert core.update_task(999, {'done': True}, db) is None
