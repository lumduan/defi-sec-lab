"""Self-test for .gitleaks.toml.

Every custom rule must FIRE on a freshly generated fake secret, and lookalike non-secrets (the local fork
endpoint, documentation placeholders, anvil's public dev keys, block hashes) must produce NO finding.

Fake secrets are random and generated at runtime into a temp dir. They are assembled from parts, so this
file itself never matches a rule. Run via scripts/test-secret-rules.sh (inside the hooks image).
"""

import json
import math
import secrets
import string
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

CONFIG = sys.argv[1] if len(sys.argv) > 1 else ".gitleaks.toml"

# anvil account 0: a PUBLIC development key (sanctioned by AGENTS.md, allowlisted in .gitleaks.toml)
ANVIL_DEV_KEY_0 = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"  # pragma: allowlist secret
WORDS = ["apple", "river", "stone", "cloud", "tiger", "piano", "orbit", "maple",
         "lemon", "quartz", "velvet", "harbor", "ember", "falcon", "meadow", "copper"]


def alnum(n: int) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n))


def hexs(n: int) -> str:
    return secrets.token_hex(n // 2)


def url(scheme: str, host: str, path: str) -> str:
    return scheme + "://" + host + path


def assign(name_parts: list[str], value: str) -> str:
    return "".join(name_parts) + "=" + value


def high_entropy_hex(n: int) -> str:
    """Hex string with Shannon entropy >= 3.6 and none of gitleaks' hex stopwords.

    generic-api-key drops candidates with entropy <= 3.5, so a low-entropy test value would make a positive
    case fail and a negative case pass for the wrong reason.
    """
    stopwords = ("000000", "aaaaaa", "dead", "feed")
    while True:
        value = hexs(n)
        counts = {c: value.count(c) for c in set(value)}
        entropy = -sum((k / n) * math.log2(k / n) for k in counts.values())
        if entropy >= 3.6 and not any(w in value for w in stopwords):
            return value


def mixed_case_hex(n: int) -> str:
    """Random hex with random letter casing (the shape of an EIP-55 checksummed address)."""
    return "".join(c.upper() if c.isalpha() and secrets.randbelow(2) else c for c in hexs(n))


S = "https"
HASH_LINE_VALUE = high_entropy_hex(40)  # identical value in both baseline cases: only the file name differs
CASES: list[tuple] = [  # (expected rule | None, label, line[, filename])
    # --- positives: (expected rule id, label, line) -------------------------------------------------
    ("rpc-url-alchemy", "Alchemy URL", assign(["RPC", "_URL"], url(S, "arb-mainnet.g.alchemy.com", "/v2/" + alnum(32)))),
    ("rpc-url-infura", "Infura URL", url(S, "arbitrum-mainnet.infura.io", "/v3/" + hexs(32))),
    ("rpc-url-quicknode", "QuickNode URL", url(S, "tiny-name.arbitrum-mainnet.quiknode.pro", "/" + hexs(40) + "/")),
    ("rpc-url-ankr", "Ankr URL", url(S, "rpc.ankr.com", "/arbitrum/" + hexs(64))),
    ("rpc-url-drpc", "dRPC URL", url(S, "lb.drpc.org", "/ogrpc?network=arbitrum&dkey=" + alnum(40))),
    ("rpc-url-chainstack", "Chainstack URL", url(S, "arbitrum-mainnet.core.chainstack.com", "/" + hexs(32))),
    ("rpc-url-blastapi", "Blast API URL", url(S, "arbitrum-one.blastapi.io", "/" + str(uuid.uuid4()))),
    ("rpc-url-tenderly", "Tenderly URL", url(S, "arbitrum.gateway.tenderly.co", "/" + alnum(24))),
    ("rpc-url-assignment", "unknown provider in *RPC* var", assign(["ARB", "_RPC", "_URL"], url(S, "rpc.unknown-provider.io", "/" + alnum(28)))),
    ("eth-private-key-assignment", "DEPLOYER_PK (default rules miss this)", assign(["DEPLOYER", "_PK"], "0x" + hexs(64))),
    ("eth-private-key-assignment", "PRIVATE_KEY", assign(["PRIVATE", "_KEY"], "0x" + hexs(64))),
    ("mnemonic-assignment", "12-word mnemonic", assign(["MNE", "MONIC"], '"' + " ".join(secrets.choice(WORDS) for _ in range(12)) + '"')),
    ("block-explorer-api-key", "Arbiscan API key", assign(["ARBISCAN", "_API", "_KEY"], alnum(34).upper())),
    ("generic-api-key", "default rule still fires on a token value", assign(["SERVICE", "_API", "_TOKEN"], alnum(40))),
    # --- negatives: (None, label, line) -> must produce no finding at all ---------------------------
    (None, "fork endpoint http://anvil:8545", assign(["ETH", "_RPC", "_URL"], url("http", "anvil", ":8545"))),
    (None, "internal API endpoint", assign(["INSPECTOR", "_RPC", "_URL"], url("http", "inspector-api", ":8000/v1"))),
    (None, "localhost endpoint", assign(["FORK", "_RPC", "_URL"], url("http", "localhost", ":8545"))),
    (None, "doc placeholder <key>", assign(["RPC", "_URL"], url(S, "arb-mainnet.g.alchemy.com", "/v2/<key>"))),
    (None, "empty value", assign(["RPC", "_URL"], "")),
    (None, "anvil dev key 0 (public)", assign(["PRIVATE", "_KEY"], "0x" + ANVIL_DEV_KEY_0)),
    (None, "anvil mnemonic (public)", assign(["MNE", "MONIC"], '"' + "test " * 11 + 'junk"')),
    (None, "block hash", assign(["block", "_hash"], "0x" + hexs(64))),
    (None, "storage word in JSON", '"raw_word": "0x' + hexs(64) + '"'),
    (None, "EVM address after a token-ish name", "stableDebtTokenAddress = 0x" + mixed_case_hex(40) + " comes from provider"),
    (None, "hashed_secret line inside .secrets.baseline", '      "hashed_' + 'secret": "' + HASH_LINE_VALUE + '",', ".secrets.baseline"),
    ("generic-api-key", "same hashed_secret line in any other file", '      "hashed_' + 'secret": "' + HASH_LINE_VALUE + '",', "notes.json"),
]


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        files: dict[str, tuple[str | None, str]] = {}
        for i, case in enumerate(CASES):
            rule, label, line = case[:3]
            case_dir = tmpdir / f"case_{i:02d}"
            case_dir.mkdir()
            (case_dir / (case[3] if len(case) > 3 else "input.txt")).write_text(line + "\n")
            files[case_dir.name] = (rule, label)
        report = tmpdir / "report.json"
        proc = subprocess.run(
            ["gitleaks", "dir", str(tmpdir), "--config", CONFIG, "--report-format", "json",
             "--report-path", str(report), "--no-banner", "--redact", "--exit-code", "0"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not report.exists():
            print("gitleaks failed to run:", proc.stderr.strip()[-500:])
            return 2
        found: dict[str, set[str]] = {}
        for f in json.loads(report.read_text() or "[]"):
            case_name = Path(f["File"]).parent.name
            if case_name in files:
                found.setdefault(case_name, set()).add(f["RuleID"])

    failures = 0
    print(f"{'result':6}  {'expect':28}  {'case':40}  found")
    for name, (rule, label) in files.items():
        got = found.get(name, set())
        ok = (rule in got) if rule else (not got)
        failures += 0 if ok else 1
        expect = rule if rule else "(no finding)"
        print(f"{'PASS' if ok else 'FAIL':6}  {expect:28}  {label:40}  {', '.join(sorted(got)) or '-'}")
    print(f"\n{len(files) - failures}/{len(files)} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
