"""Demo alert receiver; logs Alertmanager notifications and exposes recent alerts."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EVENTS = []
LOCK = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/alerts':
            return self.reply(404, {'error': 'not found'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 65536:
                return self.reply(413, {'error': 'too large'})
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            return self.reply(400, {'error': 'invalid payload'})
        with LOCK:
            EVENTS.append(data)
            del EVENTS[:-30]
        print(json.dumps({'event': 'alertmanager_webhook', 'payload': data}), flush=True)
        self.reply(200, {'received': True})

    def do_GET(self):
        if self.path != '/alerts':
            return self.reply(404, {'error': 'not found'})
        with LOCK:
            data = list(EVENTS)
        self.reply(200, {'events': data})

    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

ThreadingHTTPServer(('0.0.0.0', 9094), Handler).serve_forever()
