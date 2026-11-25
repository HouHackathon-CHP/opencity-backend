# SPDX-License-Identifier: Apache-2.0
"""Check local demo account configuration and legacy fallback."""

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from demo_accounts import ACCOUNTS, credentials  # noqa: E402


def test_every_role_can_use_its_own_credentials():
    for account in ACCOUNTS:
        values = {f"DEMO_{account}_USERNAME": f"custom-{account.lower()}",
                  f"DEMO_{account}_PASSWORD": f"secret-{account.lower()}"}
        assert credentials(values, account) == (f"custom-{account.lower()}", f"secret-{account.lower()}")


def test_account_password_is_role_specific_and_admin_requires_its_own():
    values = {"DEMO_OPERATOR_PASSWORD": "old-shared-password",
              "DEMO_DISPATCHER_USERNAME": "custom-dispatcher",
              "DEMO_DISPATCHER_PASSWORD": "role-secret"}
    assert credentials(values, "DISPATCHER") == ("custom-dispatcher", "role-secret")
    assert credentials(values, "REPORTS") == ("dxos-reports", "old-shared-password")
    with pytest.raises(ValueError, match="DEMO_ADMIN_PASSWORD"):
        credentials(values, "ADMIN")
