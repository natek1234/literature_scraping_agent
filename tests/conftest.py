"""Shared pytest fixtures and configuration for all tests."""

from __future__ import annotations

import pytest
from dotenv import load_dotenv

load_dotenv()

# Counters for the live-connection summary printed at end of session
_live_passed: list[str] = []
_live_skipped: list[str] = []
_guard_passed: list[str] = []


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: hits real external APIs — requires network access (may be slow)",
    )
    config.addinivalue_line(
        "markers",
        "live: verified a real connection and returned data (not just a credential-gated skip)",
    )


@pytest.fixture(scope="session")
def config():
    """Load the project config from CONTEXT.md (used by integration tests)."""
    from sourcing_agent.config import Config

    return Config.from_file("CONTEXT.md")


# ── Live vs guard test tracking ───────────────────────────────────────────────


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> None:  # type: ignore[return]
    """Track which live tests passed vs skipped for the terminal summary."""
    if call.when != "call":
        return

    is_live = item.get_closest_marker("live") is not None
    node_id = item.nodeid

    if call.excinfo is not None:
        # Skipped tests surface here with a Skipped exception
        if call.excinfo.type is pytest.skip.Exception:  # type: ignore[attr-defined]
            if is_live:
                _live_skipped.append(node_id)
        return

    # Test passed (no exception raised)
    if is_live:
        _live_passed.append(node_id)
    else:
        _guard_passed.append(node_id)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,  # type: ignore[name-defined]
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Print a live-connection breakdown after the normal pytest output."""
    if not (_live_passed or _live_skipped):
        return

    tw = terminalreporter
    tw.write_sep("=", "live connection summary", bold=True)

    if _live_passed:
        tw.write_line(
            f"  LIVE CONNECTED  ({len(_live_passed)} tests made real API/browser calls)",
            green=True,
            bold=True,
        )
        for nid in _live_passed:
            tw.write_line(f"    + {nid}", green=True)

    if _live_skipped:
        tw.write_line(
            f"  CREDENTIAL-SKIPPED  "
            f"({len(_live_skipped)} tests skipped — add credentials to .env)",
            yellow=True,
            bold=True,
        )
        for nid in _live_skipped:
            tw.write_line(f"    ~ {nid}", yellow=True)

    tw.write_sep(
        "-",
        f"{len(_live_passed)} live  |  {len(_live_skipped)} credential-skipped  |  "
        f"{len(_guard_passed)} guard tests passed",
    )
