# TaskPulse: SIT223/SIT753 7.3HD Jenkins DevOps Pipeline

A non-static, Python 3.12 / SQLite task-management HTTP API with real CRUD, unit and HTTP integration tests, Docker staging/production deployments, structured monitoring and automated alert delivery. The repository is a runnable **starter implementation**, not evidence that Jenkins/Docker was executed on your computer.

## Assessment mapping

| Stage | Automation and proof |
|---|---|
| Build | Git commit + Jenkins build-number image tags, `docker build`, saved image archive and ID in Jenkins artefacts. |
| Test | `pytest` unit + live HTTP integration, `pytest-cov` branch-aware 85% gate, JUnit XML. |
| Code Quality | Ruff syntax/logic lint, Radon complexity gate A-C, archived JSON trends. |
| Security | Bandit medium/high, pip-audit dependency CVEs and Trivy HIGH/CRITICAL container scan; failures block staging. Investigate, patch or document actual findings. |
| Deploy | Compose staging on localhost:18080, readiness gate and black-box CRUD smoke test. |
| Release | Re-tagged immutable image for production on localhost:18081, app version, local Git release tag, automated rollback to previous image on failed readiness or smoke. |
| Monitoring | Prometheus /metrics and /metrics/ready, production availability and 5xx alert rules, Alertmanager to live webhook receiver; validation blocks successful pipeline completion. |

## Prerequisites and limits

1. Use a **Linux Jenkins host or WSL2 Ubuntu** with Git, Python 3.12+, Python venv, Docker Engine + Compose v2 plugin, Trivy, curl, and a Jenkins controller/agent able to run Docker commands. Ensure disk space for a Docker image TAR archive, and Jenkins permissions to access Docker. Docker socket privileges are root-equivalent: only use a trusted local demo Jenkins instance. Do not expose Prometheus or the API publicly; all host ports bind to `127.0.0.1`.
2. Install Jenkins plugins: **Pipeline**, **Git**, and **JUnit**. Optional: Pipeline Stage View for visual stage evidence. Set a GitHub repository as a Jenkins *Pipeline script from SCM* project, script path `Jenkinsfile`. Use Git credentials if private. Polling every 5 minutes is configured; webhook triggers are an alternative.
3. On Jenkins host, verify: `docker version`, `docker compose version`, `trivy --version`, `python3 --version`, `git --version`, `curl --version`. The first Docker build requires network access to pull its base image, and the test/security stage installs pinned packages from PyPI. Update versions and audit the changes if scanner flags known vulnerabilities.
4. Push all repository files to your **own GitHub repo**. Grant *both marker and unit chair* appropriate access before submitting. Do not submit the downloadable ZIP alone as your GitHub URL.
5. This is a local production-like lab, not internet-hosted production. If your rubric assessor expects external infrastructure or email/Slack delivery, agree on the target and change Compose/webhook configuration accordingly. The bundled Alertmanager receiver demonstrates automatic in-system notification and retains only its latest 30 events in memory. A real team-delivery destination (email/Slack) requires credentials and an approved integration.

## Run locally before Jenkins

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest --cov=app --cov-branch --cov-report=term-missing
ruff check app tests scripts --select E4,E7,E9,F
python scripts/quality_gate.py
bandit -r app -f json -o reports/bandit.json -ll
pip-audit -r requirements-dev.txt -f json -o reports/dependencies.json
# Install trivy on the host (see official Trivy docs), then:
docker build -t taskpulse-api:local .
trivy image --exit-code 1 --severity HIGH,CRITICAL taskpulse-api:local
```

Start the local application without Docker:

```bash
DB_PATH=./tasks.db PORT=8000 python -m app.server
# http://127.0.0.1:8000/
```

## Manual Docker rehearsal (only after installing Docker)

```bash
export APP_IMAGE=taskpulse-api:local RELEASE_VERSION=local
# Build image first. Staging smoke does not touch production data.
docker compose -p taskpulse-staging -f compose.staging.yml up -d --no-build
bash scripts/wait_healthy.sh http://127.0.0.1:18080
python3 scripts/smoke.py http://127.0.0.1:18080
# Monitoring network and stack must exist before production compose.
docker network create taskpulse-monitoring
docker compose -p taskpulse-monitor -f compose.monitoring.yml up -d --build
bash scripts/release.sh
python3 scripts/check_monitoring.py
```

Open: API `http://127.0.0.1:18081/`; Prometheus `http://127.0.0.1:19090/targets` and `/alerts`; Alertmanager `http://127.0.0.1:19093/`; webhook receiver `http://127.0.0.1:19094/alerts`.

## Incident simulation (show separately in video)

```bash
bash scripts/incident_demo.sh
```

This creates a local readiness-failure flag inside the production container and waits 40 seconds, allowing the 5-second scrape/evaluation and 15-second alert `for` delay, then prints webhook events and removes the flag. Check the receiver's JSON for an event whose `status` is `firing` and alertname `TaskPulseProductionUnavailable`. Prometheus should later mark the alert resolved. **Do not claim alert delivery until you see the actual event.** Only run this against your local demonstration service.

## Security findings log (complete with actual scanner output)

| Scanner / finding | Severity | Evidence | Action / mitigation | Re-scan status |
|---|---|---|---|---|
| Bandit | [fill after scan] | `reports/bandit.json` | [fill] | [fill] |
| pip-audit | [fill after scan] | `reports/dependencies.json` | [fill] | [fill] |
| Trivy | [fill after scan] | `reports/container-security.json` | [fill] | [fill] |

If a scan fails, fix the relevant image/dependency and re-run. Never silently suppress HIGH/CRITICAL findings to force a green build. A false positive needs a written rationale and documented approved exception.

## Screenshot checklist

Capture real: Jenkins configuration SCM/script path, first and most recent pipeline runs, each of seven successful stages, archive/JUnit/coverage, Ruff/Radon, security scan reports, staging and production smoke logs, `/` with release version, Prometheus Targets `UP`, Prometheus alert `firing`, webhook receiver event and recovery. Insert representative screenshots in the template PDF; never replace a screenshot with a fabricated mock.

## Running the demo (under 10 minutes)

1. 0:00–0:50: GitHub repository, file tree, clone command, Jenkins SCM project + Jenkinsfile.
2. 0:50–2:00: project API and SQLite CRUD, Dockerfile and monitoring architecture.
3. 2:00–4:20: trigger a build; explain Build, Test, Code Quality, Security from real console and archived reports.
4. 4:20–6:10: staging smoke and production promotion with image version and rollback script.
5. 6:10–7:30: show deployed API + Prometheus Targets and rules.
6. 7:30–9:15: run `bash scripts/incident_demo.sh`; show firing notification JSON and recovery.
7. 9:15–9:50: summarize actual outcomes and known limitations (local lab, no live user notification service unless configured).

Pre-run a completed successful build and record its Jenkins console/stage view: fresh image pulls and package downloads can exceed 10 minutes. The demo must still show real execution evidence, not just code.

## Submission

Fill `7.3HD_answer_sheet_DRAFT.docx`, insert screenshots from your own Jenkins, video URL, actual GitHub URL, actual security results, and export it to PDF. Upload the PDF; confirm both tutors can view your repository and demo video. The assessment allows just two submissions in total.
