"""Enforce the TaskPulse local-demo security exception against fresh scan reports.

All findings remain in their original archived scanner reports. This gate rejects
new findings, available fixes, critical findings, expired exceptions, and scanner
errors. It is not a claim that the accepted findings are harmless.
"""

import argparse
import datetime as dt
import json
from pathlib import Path


class GateError(Exception):
    """A security policy violation or invalid scanner report."""


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GateError(f"Cannot read valid JSON from {path}: {exc}") from exc


def evaluate(bandit, dependencies, trivy, policy):
    failures = []
    observations = []

    if policy.get("schema_version") != 1 or policy.get("scope") != "local-demo-only":
        failures.append("Invalid policy schema or scope; only local-demo-only is supported")
    try:
        expiry = dt.date.fromisoformat(policy["expires_on"])
        if dt.datetime.now(dt.timezone.utc).date() > expiry:
            failures.append(f"Temporary policy expired on {expiry}")
    except (KeyError, TypeError, ValueError):
        failures.append("Policy must contain a valid expires_on date")

    # A narrowly defined exception for the container's intentional bind address.
    if not isinstance(bandit, dict) or not isinstance(bandit.get("results"), list):
        failures.append("Bandit report is missing results")
    elif bandit.get("errors"):
        failures.append("Bandit reported scanning errors")
    else:
        for issue in bandit["results"]:
            expected = (
                issue.get("test_id") == "B104"
                and issue.get("filename") == "app/server.py"
                and issue.get("issue_severity") == "MEDIUM"
                and "0.0.0.0" in issue.get("code", "")
            )
            if expected:
                observations.append("Bandit B104: intentional Docker bind; host ports must remain loopback-only")
            else:
                failures.append(
                    f"Unreviewed Bandit issue: {issue.get('test_id')} in {issue.get('filename')}"
                )

    # pip-audit's JSON format has a dependencies list with a vulns list per item.
    if not isinstance(dependencies, dict) or not isinstance(dependencies.get("dependencies"), list):
        failures.append("pip-audit report is missing dependencies")
    else:
        if dependencies.get("errors"):
            failures.append("pip-audit reported errors")
        for package in dependencies["dependencies"]:
            for vulnerability in package.get("vulns", []):
                failures.append(
                    f"Python dependency finding: {package.get('name')} {vulnerability.get('id')}"
                )

    # Fail closed unless all results are well-formed and identify the scanned image.
    results = trivy.get("Results") if isinstance(trivy, dict) else None
    if not isinstance(results, list) or not trivy.get("ArtifactName"):
        failures.append("Trivy report is missing image identity or results")
        results = []
    expected_ids = policy.get("accepted_findings", {})
    if not isinstance(expected_ids, dict):
        failures.append("Policy accepted_findings must be a mapping")
        expected_ids = {}
    allowed_pairs = {
        (vuln_id, package)
        for vuln_id, packages in expected_ids.items()
        for package in packages
    }
    seen_pairs = set()
    total = 0
    for target in results:
        for vulnerability in target.get("Vulnerabilities", []):
            total += 1
            vuln_id = vulnerability.get("VulnerabilityID")
            package = vulnerability.get("PkgName")
            pair = (vuln_id, package)
            seen_pairs.add(pair)
            severity = vulnerability.get("Severity")
            fixed_version = vulnerability.get("FixedVersion")
            status = vulnerability.get("Status")
            if severity == "CRITICAL":
                failures.append(f"CRITICAL vulnerability: {vuln_id} ({package})")
            if fixed_version:
                failures.append(f"Fix available: {vuln_id} ({package}) -> {fixed_version}")
            if pair not in allowed_pairs:
                failures.append(f"Unreviewed image finding: {vuln_id} ({package})")
            if severity != "HIGH" or status not in ("affected", "fix_deferred"):
                failures.append(f"Finding changed severity/status: {vuln_id} ({package}): {severity}/{status}")
    if total != len(seen_pairs):
        failures.append("Duplicate CVE/package entries require review")
    if total != policy.get("expected_finding_count"):
        failures.append(f"Trivy count changed: {total} vs baseline {policy.get('expected_finding_count')}")
    if seen_pairs != allowed_pairs:
        failures.append(f"Trivy baseline changed (missing={len(allowed_pairs-seen_pairs)}, new={len(seen_pairs-allowed_pairs)})")
    observations.append(f"Trivy: {total} HIGH findings matched the temporary local-demo baseline; none are resolved by this exception")
    return {"status": "FAIL" if failures else "PASS_WITH_DOCUMENTED_RESIDUAL_RISK", "scope": "local-demo-only", "image": trivy.get("ArtifactName"), "failures": sorted(set(failures)), "observations": observations, "finding_count": total, "policy_expires_on": policy.get("expires_on")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bandit", default="reports/bandit.json")
    parser.add_argument("--dependencies", default="reports/dependencies.json")
    parser.add_argument("--trivy", default="reports/container-security.json")
    parser.add_argument("--policy", default="security/local-demo-policy.json")
    parser.add_argument("--output", default="reports/security-decision.json")
    args = parser.parse_args()
    try:
        decision = evaluate(
            load_json(args.bandit), load_json(args.dependencies),
            load_json(args.trivy), load_json(args.policy)
        )
    except GateError as exc:
        decision = {"status": "FAIL", "failures": [str(exc)]}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2))
    return 0 if decision["status"] == "PASS_WITH_DOCUMENTED_RESIDUAL_RISK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
