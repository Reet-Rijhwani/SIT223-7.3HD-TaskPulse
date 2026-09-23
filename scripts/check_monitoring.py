"""Pipeline gate: confirm Prometheus has scraped production and has a configured alert rule."""
import json
import urllib.request

base = 'http://127.0.0.1:19090'
def get(path):
    with urllib.request.urlopen(base+path, timeout=5) as response:
        return json.load(response)

targets = get('/api/v1/targets')['data']['activeTargets']
for job in ('taskpulse-production', 'taskpulse-production-readiness'):
    matches = [t for t in targets if t['labels'].get('job') == job]
    assert len(matches) == 1 and matches[0]['health'] == 'up', (job, matches)
rules = get('/api/v1/rules')['data']['groups']
assert any(rule['name'] == 'TaskPulseProductionUnavailable' for group in rules for rule in group['rules'])
print('PASS: metrics target, readiness target and production alert rule')
