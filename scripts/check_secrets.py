"""Fail when Git-tracked files contain likely credentials or unsafe filenames."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class SecretFinding:
    path: Path
    rule: str


CONTENT_RULES = {
    "private key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "Clerk or Stripe secret key": re.compile(rb"\bsk_(?:test|live)_[A-Za-z0-9]{20,}"),
    "GitHub token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Google API key": re.compile(rb"\bAIza[A-Za-z0-9_-]{30,}\b"),
}
SENSITIVE_SUFFIXES = {".key", ".p12", ".pfx", ".pem"}
SENSITIVE_NAMES = {"credentials.json", "id_rsa", "id_ed25519", "secrets.json"}


def has_sensitive_name(path: Path) -> bool:
    name = path.name.lower()
    if name == ".env":
        return True
    if name.startswith(".env.") and not name.endswith(".example"):
        return True
    return name in SENSITIVE_NAMES or path.suffix.lower() in SENSITIVE_SUFFIXES


def scan_paths(paths: list[Path]) -> list[SecretFinding]:
    findings = []
    for path in paths:
        if has_sensitive_name(path):
            findings.append(SecretFinding(path, "sensitive filename"))
        try:
            content = (
                os.readlink(path).encode("utf-8")
                if path.is_symlink()
                else path.read_bytes()
            )
        except (FileNotFoundError, IsADirectoryError):
            continue
        for rule, pattern in CONTENT_RULES.items():
            if pattern.search(content):
                findings.append(SecretFinding(path, rule))
    return findings


def tracked_paths(project_root: Path = PROJECT_ROOT) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=project_root,
        capture_output=True,
        check=True,
        timeout=10,
    )
    return [
        project_root / Path(raw_path.decode("utf-8"))
        for raw_path in result.stdout.split(b"\0")
        if raw_path
    ]


def main() -> None:
    findings = scan_paths(tracked_paths())
    if findings:
        print("Potential secrets found in tracked files:")
        for finding in findings:
            print(f"- {finding.path.relative_to(PROJECT_ROOT)} ({finding.rule})")
        raise SystemExit(1)
    print("Tracked-file secret scan passed.")


if __name__ == "__main__":
    main()
