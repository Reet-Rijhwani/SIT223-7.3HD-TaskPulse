
"""Deployable HTTP API with health, CRUD and Prometheus-compatible metrics."""

import json
import os
import sqlite3
import tempfile
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from app import core

VERSION = os.environ.get('APP_VERSION', 'development')
COUNTS = Counter()
COUNT_LOCK = threading.Lock()
STARTED = time.monotonic()

DEFAULT_FAILURE_FLAG = os.path.join(
    tempfile.gettempdir(),
    'taskpulse-unhealthy'
)


def is_unhealthy():
    """Check the current failure flag for health and monitoring tests."""
    failure_flag = os.environ.get(
        'FAILURE_FLAG',
        DEFAULT_FAILURE_FLAG
    )
    return os.path.exists(failure_flag)


class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(
            json.dumps({
                'event': 'http',
                'message': fmt % args
            }),
            flush=True
        )

    def respond(
        self,
        status,
        data,
        content_type='application/json; charset=utf-8'
    ):
        raw = (
            json.dumps(data)
            if not isinstance(data, str)
            else data
        ).encode()

        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

        with COUNT_LOCK:
            COUNTS[
                (self.command, urlsplit(self.path).path, status)
            ] += 1

    def body(self):
        length = int(
            self.headers.get('Content-Length', '0')
        )

        if length > 8192:
            raise ValueError('request body exceeds 8 KiB')

        try:
            return json.loads(
                self.rfile.read(length)
            )

        except (ValueError, UnicodeDecodeError) as ex:
            raise ValueError('invalid JSON') from ex

    def do_GET(self):
        path = urlsplit(self.path).path

        if path == '/health/live':
            return self.respond(
                200,
                {
                    'status': 'alive',
                    'version': VERSION
                }
            )

        if path == '/health/ready':

            if is_unhealthy():
                return self.respond(
                    503,
                    {'status': 'unhealthy'}
                )

            try:
                with core.connect() as db:
                    db.execute(
                        'SELECT 1 FROM tasks LIMIT 1'
                    ).fetchone()

                return self.respond(
                    200,
                    {
                        'status': 'ready',
                        'version': VERSION
                    }
                )

            except sqlite3.Error:
                return self.respond(
                    503,
                    {'status': 'database unavailable'}
                )

        if path == '/metrics/ready':

            if is_unhealthy():
                return self.respond(
                    503,
                    'taskpulse_ready 0\n',
                    'text/plain; version=0.0.4; charset=utf-8'
                )

            try:
                with core.connect() as db:
                    db.execute(
                        'SELECT 1 FROM tasks LIMIT 1'
                    ).fetchone()

                return self.respond(
                    200,
                    '# TYPE taskpulse_ready gauge\n'
                    'taskpulse_ready 1\n',
                    'text/plain; version=0.0.4; charset=utf-8'
                )

            except sqlite3.Error:
                return self.respond(
                    503,
                    'taskpulse_ready 0\n',
                    'text/plain; version=0.0.4; charset=utf-8'
                )

        if path == '/metrics':

            with COUNT_LOCK:
                sample = list(COUNTS.items())

            lines = [
                '# HELP taskpulse_requests_total HTTP requests handled',
                '# TYPE taskpulse_requests_total counter'
            ]

            for (method, route, code), count in sorted(sample):
                lines.append(
                    f'taskpulse_requests_total{{method="{method}",'
                    f'route="{route}",status="{code}"}} {count}'
                )

            lines += [
                '# HELP taskpulse_uptime_seconds Process uptime',
                '# TYPE taskpulse_uptime_seconds gauge',
                f'taskpulse_uptime_seconds '
                f'{time.monotonic() - STARTED:.2f}'
            ]

            return self.respond(
                200,
                '\n'.join(lines) + '\n',
                'text/plain; version=0.0.4; charset=utf-8'
            )

        if path == '/api/tasks':
            return self.respond(
                200,
                {'tasks': core.list_tasks()}
            )

        if path == '/':
            return self.respond(
                200,
                {
                    'service': 'TaskPulse',
                    'version': VERSION,
                    'endpoints': [
                        '/api/tasks',
                        '/health/ready',
                        '/metrics'
                    ]
                }
            )

        return self.respond(
            404,
            {'error': 'not found'}
        )

    def do_POST(self):

        if urlsplit(self.path).path != '/api/tasks':
            return self.respond(
                404,
                {'error': 'not found'}
            )

        try:
            return self.respond(
                201,
                core.add_task(self.body())
            )

        except ValueError as ex:
            return self.respond(
                400,
                {'error': str(ex)}
            )

    def do_PATCH(self):

        try:
            task_id = self.task_id()
            task = core.update_task(
                task_id,
                self.body()
            )

            return (
                self.respond(200, task)
                if task
                else self.respond(
                    404,
                    {'error': 'task not found'}
                )
            )

        except ValueError as ex:
            return self.respond(
                400,
                {'error': str(ex)}
            )

    def do_DELETE(self):

        try:
            task_id = self.task_id()

            return (
                self.respond(204, '')
                if core.delete_task(task_id)
                else self.respond(
                    404,
                    {'error': 'task not found'}
                )
            )

        except ValueError as ex:
            return self.respond(
                400,
                {'error': str(ex)}
            )

    def task_id(self):

        segments = urlsplit(
            self.path
        ).path.split('/')

        if (
            len(segments) != 4
            or segments[1:3] != ['api', 'tasks']
            or not segments[3].isdigit()
            or int(segments[3]) < 1
        ):
            raise ValueError(
                'expected /api/tasks/{positive integer}'
            )

        return int(segments[3])


def main():

    core.init_db()

    host = os.environ.get(
        'HOST',
        '0.0.0.0'
    )

    port = int(
        os.environ.get('PORT', '8000')
    )

    print(
        json.dumps({
            'event': 'startup',
            'version': VERSION,
            'port': port
        }),
        flush=True
    )

    ThreadingHTTPServer(
        (host, port),
        Handler
    ).serve_forever()


if __name__ == '__main__':
    main()