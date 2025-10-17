"""Regression tests for host dependency declarations."""

import build
import host_bootstrap


def test_flex_included_in_dependency_checks() -> None:
    """The kernel build relies on flex being available on the host."""

    assert "flex" in build.ALL_DEPENDENCIES
    assert "flex" in build.DEPENDENCY_HINTS
    assert "flex" in host_bootstrap.APT_PACKAGE_MAP
    assert "flex" in host_bootstrap.DNF_PACKAGE_MAP


def test_bison_included_in_dependency_checks() -> None:
    """The kernel configuration step requires bison."""

    assert "bison" in build.ALL_DEPENDENCIES
    assert "bison" in build.DEPENDENCY_HINTS
    assert "bison" in host_bootstrap.APT_PACKAGE_MAP
    assert "bison" in host_bootstrap.DNF_PACKAGE_MAP
