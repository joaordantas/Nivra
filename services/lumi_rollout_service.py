from __future__ import annotations

import os


VALID_LUMI_ROLLOUT_MODES = frozenset({"off", "internal", "allowlist", "all"})


def _strict_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() == "true"


def lumi_rollout_mode() -> str:
    """Return the effective fail-closed rollout mode.

    LUMI_PUBLIC_ENABLED remains the emergency kill switch. A missing or invalid
    rollout mode never widens access.
    """
    if not _strict_true("LUMI_PUBLIC_ENABLED"):
        return "off"
    configured = os.environ.get("LUMI_ROLLOUT_MODE", "off").strip().lower()
    return configured if configured in VALID_LUMI_ROLLOUT_MODES else "off"


def lumi_rollout_user_ids() -> frozenset[int]:
    raw = os.environ.get("LUMI_ROLLOUT_USER_IDS", "").strip()
    if not raw:
        return frozenset()
    values: set[int] = set()
    for item in raw.split(","):
        candidate = item.strip()
        if not candidate.isdecimal() or int(candidate) < 1:
            return frozenset()
        values.add(int(candidate))
    return frozenset(values)


def lumi_access_allowed(authenticated_user_id: int) -> bool:
    mode = lumi_rollout_mode()
    if mode == "all":
        return True
    if mode in {"internal", "allowlist"}:
        return authenticated_user_id in lumi_rollout_user_ids()
    return False
