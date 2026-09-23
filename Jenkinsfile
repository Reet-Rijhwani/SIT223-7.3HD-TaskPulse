pipeline {
    agent any
    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        skipDefaultCheckout(true)
    }
    triggers { pollSCM('H/5 * * * *') }
    environment {
        APP = 'taskpulse'
        IMAGE = 'taskpulse-api'
        STAGING_URL = 'http://127.0.0.1:18080'
        PRODUCTION_URL = 'http://127.0.0.1:18081'
    }
    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.SHORT_SHA = sh(script: 'git rev-parse --short=8 HEAD', returnStdout: true).trim()
                    env.RELEASE_VERSION = "${env.BUILD_NUMBER}-${env.SHORT_SHA}"
                    env.APP_IMAGE = "${env.IMAGE}:${env.RELEASE_VERSION}"
                }
            }
        }
        stage('Build') {
            steps {
                sh '''set -eu
                    mkdir -p reports
                    docker build --pull --label org.opencontainers.image.revision="$(git rev-parse HEAD)" -t "$APP_IMAGE" .
                    docker image inspect "$APP_IMAGE" --format '{{.Id}}' > reports/image-id.txt
                    printf '%s\n' "$APP_IMAGE" > reports/image-tag.txt
                    docker save "$APP_IMAGE" | gzip > "reports/image-${RELEASE_VERSION}.tar.gz"
                '''
                archiveArtifacts artifacts: 'reports/image-*.tar.gz,reports/image-*.txt', fingerprint: true
            }
        }
        stage('Test') {
            steps {
                sh '''set -eu
                    python3 -m venv .venv
                    . .venv/bin/activate
                    python -m pip install --upgrade pip
                    python -m pip install -r requirements-dev.txt
                    mkdir -p reports
                    python -m pytest --junitxml=reports/junit.xml --cov=app --cov-branch --cov-report=xml:reports/coverage.xml --cov-report=term-missing
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                    archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/coverage.xml'
                }
            }
        }
        stage('Code Quality') {
            steps {
                sh '''set -eu
                    . .venv/bin/activate
                    ruff check app tests scripts --select E4,E7,E9,F --output-format json > reports/ruff.json
                    python scripts/quality_gate.py
                '''
                archiveArtifacts artifacts: 'reports/ruff.json,reports/complexity.json', fingerprint: true
            }
        }
        stage('Security') {
            steps {
                sh '''set -eu
                    . .venv/bin/activate
                    mkdir -p reports
                    # Preserve complete findings. The policy script, not the scanner's
                    # exit code alone, makes the final security decision.
                    set +e
                    bandit -r app -f json -o reports/bandit.json -ll
                    bandit_status=$?
                    pip-audit -r requirements-dev.txt -f json -o reports/dependencies.json
                    audit_status=$?
                    set -e
                    if [ "$bandit_status" -gt 1 ] || [ "$audit_status" -gt 1 ]; then
                        echo 'A security scanner failed to execute correctly.' >&2
                        exit 1
                    fi
                    trivy image --scanners vuln --severity HIGH,CRITICAL --format json --output reports/container-security.json "$APP_IMAGE"
                    python scripts/security_gate.py
                '''
            }
            post {
                always {
                    archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/bandit.json,reports/dependencies.json,reports/container-security.json,reports/security-decision.json'
                }
            }
        }
        stage('Deploy (staging)') {
            steps {
                sh '''set -eu
                    docker compose -p taskpulse-staging -f compose.staging.yml up -d --no-build --force-recreate
                    bash scripts/wait_healthy.sh "$STAGING_URL"
                    python3 scripts/smoke.py "$STAGING_URL"
                '''
            }
        }
        stage('Release (production)') {
            steps {
                sh '''set -eu
                    docker network inspect taskpulse-monitoring >/dev/null 2>&1 || docker network create taskpulse-monitoring
                    docker compose -p taskpulse-monitor -f compose.monitoring.yml up -d --build
                    bash scripts/release.sh
                    docker tag "$APP_IMAGE" "${IMAGE}:stable"
                    printf '%s\n' "$RELEASE_VERSION" > reports/release-version.txt
                    git tag -f "release-${RELEASE_VERSION}" "$(git rev-parse HEAD)"
                '''
                archiveArtifacts artifacts: 'reports/release-version.txt,release-history.txt', allowEmptyArchive: true
            }
        }
        stage('Monitoring & Alerting') {
            steps {
                sh '''set -eu
                    for i in $(seq 1 30); do
                        if python3 scripts/check_monitoring.py; then exit 0; fi
                        sleep 3
                    done
                    exit 1
                '''
            }
        }
    }
    post {
        success { echo 'All seven assessment stages completed under the documented local-demo security policy. Residual HIGH findings remain.' }
        failure { echo 'Pipeline failed; inspect the failing stage and archived reports before promotion.' }
        always { archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/**' }
    }
}
