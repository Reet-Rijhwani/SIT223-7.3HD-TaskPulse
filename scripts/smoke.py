"""Black-box deployment verification including persistent CRUD and metrics."""
import json
import sys
import urllib.error
import urllib.request
import uuid

url = sys.argv[1].rstrip('/')

def call(path, method='GET', payload=None):
    req = urllib.request.Request(url+path, method=method, data=json.dumps(payload).encode() if payload is not None else None, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=5) as res:
        return res.status, json.loads(res.read() or b'null')

assert call('/health/ready')[0] == 200
name = 'smoke-' + uuid.uuid4().hex[:8]
status, task = call('/api/tasks', 'POST', {'title': name})
assert status == 201 and task['title'] == name
assert call(f"/api/tasks/{task['id']}", 'PATCH', {'done': True})[1]['done']
assert call(f"/api/tasks/{task['id']}", 'DELETE')[0] == 204
assert b'taskpulse_requests_total' in urllib.request.urlopen(url+'/metrics', timeout=5).read()
print('PASS: readiness, create, update, delete and metrics', url)
