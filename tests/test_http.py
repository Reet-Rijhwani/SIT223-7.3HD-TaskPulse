
import json
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest

from app import core, server


@contextmanager
def running_server(tmp_path):
    original = core.DB_PATH
    original_flag = server.os.environ.get('FAILURE_FLAG')

    core.DB_PATH = str(tmp_path / 'integration.db')
    server.os.environ['FAILURE_FLAG'] = str(tmp_path / 'unhealthy')

    core.init_db()

    instance = ThreadingHTTPServer(
        ('127.0.0.1', 0),
        server.Handler
    )

    thread = Thread(
        target=instance.serve_forever,
        daemon=True
    )

    thread.start()

    try:
        yield f'http://127.0.0.1:{instance.server_port}', tmp_path

    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=3)

        core.DB_PATH = original

        if original_flag is None:
            server.os.environ.pop('FAILURE_FLAG', None)
        else:
            server.os.environ['FAILURE_FLAG'] = original_flag


def request(url, path, method='GET', payload=None):
    data = json.dumps(payload).encode() if payload is not None else None

    req = urllib.request.Request(
        url + path,
        data=data,
        method=method,
        headers={'Content-Type': 'application/json'}
    )

    try:
        with urllib.request.urlopen(req, timeout=3) as res:
            return res.status, json.loads(res.read() or b'null')

    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b'null')


def test_http_crud_and_metrics(tmp_path):
    with running_server(tmp_path) as (url, _):

        assert request(url, '/health/ready')[0] == 200

        status, task = request(
            url,
            '/api/tasks',
            'POST',
            {'title': 'Integration test'}
        )

        assert status == 201

        assert request(url, '/api/tasks')[1]['tasks'][0]['id'] == task['id']

        assert request(
            url,
            f"/api/tasks/{task['id']}",
            'PATCH',
            {'done': True}
        )[1]['done']

        assert request(
            url,
            f"/api/tasks/{task['id']}",
            'DELETE'
        )[0] == 204

        assert request(url, '/api/tasks')[1]['tasks'] == []

        assert b'taskpulse_requests_total' in urllib.request.urlopen(
            url + '/metrics'
        ).read()


def test_http_invalid_and_failure(tmp_path):
    with running_server(tmp_path) as (url, location):

        assert request(
            url,
            '/api/tasks',
            'POST',
            {'title': ''}
        )[0] == 400

        assert request(
            url,
            '/api/tasks/999',
            'PATCH',
            {'done': True}
        )[0] == 404

        (location / 'unhealthy').touch()

        assert request(url, '/health/ready')[0] == 503

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url + '/metrics/ready')

        assert exc_info.value.code == 503


def test_additional_routes(tmp_path):
    with running_server(tmp_path) as (url, _):

        assert request(url, '/')[0] == 200

        assert request(url, '/health/live')[0] == 200

        assert request(url, '/missing')[0] == 404

        assert request(
            url,
            '/unknown',
            'POST',
            {'x': 1}
        )[0] == 404

        assert request(
            url,
            '/api/tasks/not-a-number',
            'PATCH',
            {'done': True}
        )[0] == 400

        assert request(
            url,
            '/api/tasks/not-a-number',
            'DELETE'
        )[0] == 400

        with urllib.request.urlopen(url + '/metrics/ready') as response:
            assert response.status == 200
            assert b'taskpulse_ready 1' in response.read()

        assert request(
            url,
            '/api/tasks',
            'POST',
            {'title': 'x' * 121}
        )[0] == 400