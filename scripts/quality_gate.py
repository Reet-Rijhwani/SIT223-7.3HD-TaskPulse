"""Fail the build on complexity grade D/E/F; store trend-friendly JSON output."""
import json
import subprocess
import sys
from pathlib import Path

Path('reports').mkdir(exist_ok=True)
result = subprocess.run(['radon', 'cc', '--json', 'app'], capture_output=True, text=True, check=True)
Path('reports/complexity.json').write_text(result.stdout)
blocks = [entry for entries in json.loads(result.stdout).values() for entry in entries]
bad = [f"{x['name']} ({x['rank']})" for x in blocks if x['rank'] not in 'ABC']
print(f'Complexity gate: {len(blocks)} blocks; unacceptable: {bad}')
sys.exit(bool(bad))
