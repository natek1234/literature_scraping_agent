"""Shared pytest fixtures and configuration for all tests."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: hits real external APIs — requires network access (may be slow)",
    )


@pytest.fixture(scope="session")
def config():
    """Load the project config from CONTEXT.md (used by integration tests)."""
    from sourcing_agent.config import Config

    return Config.from_file("CONTEXT.md")
