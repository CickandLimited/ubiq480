"""Regression tests for host dependency declarations."""

import build
import host_bootstrap


def test_flex_included_in_dependency_checks() -> None:
    """The kernel build relies on flex being available on the host."""

    assert "flex" in build.ALL_DEPENDENCIES
    assert "flex" in build.DEPENDENCY_HINTS
    assert "flex" in host_bootstrap.APT_PACKAGE_MAP
    assert "flex" in host_bootstrap.DNF_PACKAGE_MAP
