#!/usr/bin/env python3
"""Generate verify-hardware-measurements (SPEC §6) fixtures.

Stateless pure-function fixtures — no key material, no cert chains. Just
enclave_measurement + hardware_measurements list, with the expected match
or rejection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
VECTORS_DIR = REPO_ROOT / "vectors" / "hardware-measurements"

TDX_URI = "https://tinfoil.sh/predicate/tdx-guest/v2"
SEV_URI = "https://tinfoil.sh/predicate/sev-snp-guest/v2"

# Stable values across fixtures. 96 hex chars = 48 bytes.
MRTD_A = "a" * 96
MRTD_B = "b" * 96
MRTD_C = "c" * 96
RTMR0_A = "1" * 96
RTMR0_B = "2" * 96
RTMR0_C = "3" * 96
RTMR1 = "d" * 96
RTMR2 = "e" * 96
RTMR3_ZERO = "0" * 96


def write_fixture(
    *,
    fixture_id: str,
    title: str,
    spec_refs: list[str],
    notes: str,
    enclave_measurement: dict[str, Any],
    hardware_measurements: list[dict[str, str]],
    expected_match: dict[str, str] | None,
    rejection_code: str | list[str] | None = None,
) -> None:
    input_payload = {
        "schema_version": "1",
        "enclave_measurement": enclave_measurement,
        "hardware_measurements": hardware_measurements,
    }
    if expected_match is not None:
        expected = {
            "stage": "verify-hardware-measurements",
            "accepted": True,
            "outputs": {
                "matched_id": expected_match["id"],
                "matched_mrtd": expected_match["mrtd"].lower(),
                "matched_rtmr0": expected_match["rtmr0"].lower(),
            },
        }
        expected_exit = 0
    else:
        expected = {
            "stage": "verify-hardware-measurements",
            "accepted": False,
            "rejection": {"code": rejection_code},
        }
        expected_exit = 10

    dst = VECTORS_DIR / fixture_id
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "input.json").write_text(json.dumps(input_payload, indent=2))
    (dst / "expected.json").write_text(json.dumps(expected, indent=2))

    manifest = (
        f"id: {fixture_id}\n"
        f"stage: verify-hardware-measurements\n"
        f"title: |\n  {title}\n"
        f"spec_refs: {json.dumps(spec_refs)}\n"
        f"expects:\n"
        f"  exit_code: {expected_exit}\n"
    )
    if rejection_code is not None:
        manifest += f"  rejection_code: {json.dumps(rejection_code)}\n"
    manifest += "required_capabilities: {}\n"
    manifest += "fixture_kind: synthetic\n"
    manifest += "notes: |\n"
    for line in notes.strip().splitlines():
        manifest += f"  {line}\n"
    (dst / "manifest.yaml").write_text(manifest)


def main() -> None:
    VECTORS_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Happy path ------------------------------------------------------
    write_fixture(
        fixture_id="200-hardware-match-single",
        title="Single hardware measurement matching the enclave's MRTD+RTMR0 → accept.",
        spec_refs=["6.3"],
        notes="SPEC §6.3 happy path with a 1-entry hw list.",
        enclave_measurement={
            "type": TDX_URI,
            "registers": [MRTD_A, RTMR0_A, RTMR1, RTMR2, RTMR3_ZERO],
        },
        hardware_measurements=[{"id": "platform-a@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A}],
        expected_match={"id": "platform-a@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A},
    )

    write_fixture(
        fixture_id="201-hardware-match-second-of-three",
        title="Three hw entries; enclave matches the second → accept and return that entry.",
        spec_refs=["6.3"],
        notes=(
            "SPEC §6.3 step 3: 'Iterate ... return the first match'.\n"
            "Catches an SDK that always returns measurements[0] regardless of value."
        ),
        enclave_measurement={
            "type": TDX_URI,
            "registers": [MRTD_B, RTMR0_B, RTMR1, RTMR2, RTMR3_ZERO],
        },
        hardware_measurements=[
            {"id": "platform-a@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A},
            {"id": "platform-b@dig", "mrtd": MRTD_B, "rtmr0": RTMR0_B},
            {"id": "platform-c@dig", "mrtd": MRTD_C, "rtmr0": RTMR0_C},
        ],
        expected_match={"id": "platform-b@dig", "mrtd": MRTD_B, "rtmr0": RTMR0_B},
    )

    write_fixture(
        fixture_id="202-hardware-match-returns-first-of-duplicate",
        title="Two hw entries with identical MRTD+RTMR0 — first match returned per §6.3.",
        spec_refs=["6.3"],
        notes=(
            "SPEC §6.3 step 3 is 'first match' — when two entries are equivalent\n"
            "the SDK MUST return the one with the lower index. Fixture has two\n"
            "entries with the same MRTD+RTMR0 but different ids; expects the\n"
            "first id."
        ),
        enclave_measurement={
            "type": TDX_URI,
            "registers": [MRTD_A, RTMR0_A, RTMR1, RTMR2, RTMR3_ZERO],
        },
        hardware_measurements=[
            {"id": "platform-a-first@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A},
            {"id": "platform-a-second@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A},
        ],
        expected_match={"id": "platform-a-first@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A},
    )

    # ---- Rejection cases -------------------------------------------------
    write_fixture(
        fixture_id="210-hardware-no-match",
        title="No hw entry matches → HARDWARE_NO_MATCH.",
        spec_refs=["6.3"],
        notes="SPEC §6.3 step 4: 'If no match is found, verification MUST fail.'",
        enclave_measurement={
            "type": TDX_URI,
            "registers": [MRTD_A, RTMR0_A, RTMR1, RTMR2, RTMR3_ZERO],
        },
        hardware_measurements=[
            {"id": "platform-b@dig", "mrtd": MRTD_B, "rtmr0": RTMR0_B},
            {"id": "platform-c@dig", "mrtd": MRTD_C, "rtmr0": RTMR0_C},
        ],
        expected_match=None,
        rejection_code="HARDWARE_NO_MATCH",
    )

    write_fixture(
        fixture_id="211-hardware-empty-list",
        title="Empty hw list — trivially no match → reject.",
        spec_refs=["6.3"],
        notes=(
            "Empty list trivially has no match per §6.3 step 3, fails at step 4.\n"
            "Catches an SDK that returns the zero-value HardwareMeasurement struct\n"
            "instead of erroring on an empty input list."
        ),
        enclave_measurement={
            "type": TDX_URI,
            "registers": [MRTD_A, RTMR0_A, RTMR1, RTMR2, RTMR3_ZERO],
        },
        hardware_measurements=[],
        expected_match=None,
        rejection_code="HARDWARE_NO_MATCH",
    )

    write_fixture(
        fixture_id="212-hardware-mrtd-matches-rtmr0-doesnt",
        title="MRTD matches but RTMR0 differs → reject.",
        spec_refs=["6.3"],
        notes=(
            "Both MRTD and RTMR0 must match per §6.3 step 3 (the AND condition).\n"
            "Catches an SDK that only checks MRTD."
        ),
        enclave_measurement={
            "type": TDX_URI,
            "registers": [MRTD_A, RTMR0_A, RTMR1, RTMR2, RTMR3_ZERO],
        },
        hardware_measurements=[
            {"id": "platform-a-wrong-rtmr0@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_B},
        ],
        expected_match=None,
        rejection_code="HARDWARE_NO_MATCH",
    )

    write_fixture(
        fixture_id="213-hardware-rtmr0-matches-mrtd-doesnt",
        title="RTMR0 matches but MRTD differs → reject.",
        spec_refs=["6.3"],
        notes="Symmetric to 212: catches an SDK that only checks RTMR0.",
        enclave_measurement={
            "type": TDX_URI,
            "registers": [MRTD_A, RTMR0_A, RTMR1, RTMR2, RTMR3_ZERO],
        },
        hardware_measurements=[
            {"id": "platform-wrong-mrtd@dig", "mrtd": MRTD_B, "rtmr0": RTMR0_A},
        ],
        expected_match=None,
        rejection_code="HARDWARE_NO_MATCH",
    )

    # ---- Input shape validation ------------------------------------------
    write_fixture(
        fixture_id="220-enclave-wrong-type-sev",
        title="enclave_measurement.type is SEV not TDX → reject as type-invalid.",
        spec_refs=["6.3"],
        notes=(
            "SPEC §6.3 step 1: 'The enclave measurement MUST be of type\n"
            "TdxGuestV2 with exactly 5 registers.' Hardware-measurement\n"
            "matching is TDX-only (§6 first paragraph)."
        ),
        enclave_measurement={"type": SEV_URI, "registers": [MRTD_A]},
        hardware_measurements=[
            {"id": "platform-a@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A},
        ],
        expected_match=None,
        rejection_code="ENCLAVE_MEASUREMENT_TYPE_INVALID",
    )

    write_fixture(
        fixture_id="221-enclave-tdx-register-count-3",
        title="TDX enclave_measurement with only 3 registers → reject.",
        spec_refs=["6.3"],
        notes=(
            "SPEC §6.3 step 1 requires exactly 5 registers. Anything else\n"
            "is rejected before the iteration starts."
        ),
        enclave_measurement={"type": TDX_URI, "registers": [MRTD_A, RTMR0_A, RTMR1]},
        hardware_measurements=[
            {"id": "platform-a@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A},
        ],
        expected_match=None,
        rejection_code=[
            "ENCLAVE_REGISTER_COUNT_INVALID",
            # sigstore-go's VerifyHardware checks `< 2` so 3 still passes that
            # check and falls through to the matching step where MRTD does
            # match → ACCEPT. We accept either branch (count-validate up-front,
            # or fall through). Note: this is a SPEC §6.3-step-1 strict-read
            # vs. liberal-read divergence worth documenting.
            "HARDWARE_NO_MATCH",
        ],
    )

    write_fixture(
        fixture_id="222-enclave-tdx-empty-registers",
        title="TDX enclave_measurement with 0 registers → reject.",
        spec_refs=["6.3"],
        notes="Edge of 221: no registers at all.",
        enclave_measurement={"type": TDX_URI, "registers": []},
        hardware_measurements=[
            {"id": "platform-a@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A},
        ],
        expected_match=None,
        rejection_code="ENCLAVE_REGISTER_COUNT_INVALID",
    )

    # ---- §7.3 lowercase carry-over ---------------------------------------
    write_fixture(
        fixture_id="230-hardware-case-normalization",
        title="Uppercase MRTD/RTMR0 in either side must match — §7.3 lowercase normalization.",
        spec_refs=["6.3", "7.3"],
        notes=(
            "SPEC §7.3 'Implementations MUST normalize register values to\n"
            "lowercase before any comparison'. enclave has uppercase MRTD,\n"
            "hw has uppercase RTMR0 — both must normalize to lowercase\n"
            "before the equality check."
        ),
        enclave_measurement={
            "type": TDX_URI,
            "registers": [MRTD_A.upper(), RTMR0_A, RTMR1, RTMR2, RTMR3_ZERO],
        },
        hardware_measurements=[
            {"id": "platform-mixed-case@dig", "mrtd": MRTD_A, "rtmr0": RTMR0_A.upper()},
        ],
        expected_match={
            "id": "platform-mixed-case@dig",
            "mrtd": MRTD_A,
            "rtmr0": RTMR0_A,
        },
    )

    print("Wrote hardware-measurement fixtures:")
    for d in sorted(VECTORS_DIR.iterdir()):
        if d.is_dir():
            print(f"  {d.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
