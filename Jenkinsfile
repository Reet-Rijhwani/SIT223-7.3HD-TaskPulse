pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); buildDiscarder(logRotator(numToKeepStr: '20')); skipDefaultCheckout(true) }
  triggers { pollSCM('H/5 * * * *') }
  environment {
    APP = 'taskpulse'
    IMAGE = 'taskpulse-api'
    STAGING_URL = 'http://127.0.0.1:18080'
    PRODUCTION_URL = 'http://127.0.0.1:18081'
  }
  stages {
    stage('Checkout') {
      steps { checkout scm; script { env.SHORT_SHA = sh(script: 'git rev-parse --short=8 HEAD', returnStdout: true).trim(); env.RELEASE_VERSION = "${env.BUILD_NUMBER}-${env.SHORT_SHA}"; env.APP_IMAGE = "${env.IMAGE}:${env.RELEASE_VERSION}" } }
    }
    stage('Build') {
      steps {
        sh '''set -eu
          docker build --pull --label org.opencontainers.image.revision="$(git rev-parse HEAD)" -t "$APP_IMAGE" .
          mkdir -p reports
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
          pip install -r requirements-dev.txt
          mkdir -p reports
          pytest --junitxml=reports/junit.xml --cov=app --cov-branch --cov-report=xml:reports/coverage.xml --cov-report=term-missing
        '''
      }
      post { always { junit allowEmptyResults: true, testResults: 'reports/junit.xml'; archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/coverage.xml' } }
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
          bandit -r app -f json -o reports/bandit.json -ll
          pip-audit -r requirements-dev.txt -f json -o reports/dependencies.json
          trivy image --exit-code 1 --severity HIGH,CRITICAL --format json --output reports/container-security.json "$APP_IMAGE"
        '''
      }
      post { always { archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/bandit.json,reports/dependencies.json,reports/container-security.json' } }
    }
    stage('Deploy (staging)') {
      steps {
        sh '''set -eu
          docker compose -p taskpulse-staging -f compose.staging.yml up -d --no-build --force-recreate
          ./scripts/wait_healthy.sh "$STAGING_URL"
          python3 scripts/smoke.py "$STAGING_URL"
        '''
      }
    }
    stage('Release (production)') {
      steps {
        sh '''set -eu
          docker network create taskpulse-monitoring 2>/dev/null || true
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
    success { echo 'All seven assessment stages passed. Incident simulation can be demonstrated separately.' }
    failure { echo 'Pipeline failed; inspect the failing stage and archived reports before promotion.' }
    always { archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/**' }
  }
}
