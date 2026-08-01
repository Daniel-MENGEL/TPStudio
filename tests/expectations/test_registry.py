from dataclasses import FrozenInstanceError
import inspect

import pytest

import tpstudio.expectations.models as expectation_models
import tpstudio.expectations.registry as expectation_registry
from tpstudio.expectations import (
    ExpectedConclusion,
    ExpectationRegistry,
    ExpectationSet,
)


def _set(identifier: str) -> ExpectationSet:
    return ExpectationSet(
        identifier,
        f"Set {identifier}",
        conclusions=(ExpectedConclusion(f"{identifier}-c", "Conclusion", "A."),),
    )


def test_registry_is_immutable_ordered_and_searchable() -> None:
    first = _set("first")
    second = _set("second")
    registry = ExpectationRegistry((first, second))

    assert tuple(registry) == (first, second)
    assert len(registry) == 2
    assert registry.get("second") is second
    assert registry.expectation_set_by_id("first") is first
    assert registry.get("unknown") is None
    with pytest.raises(FrozenInstanceError):
        registry.expectation_sets = ()  # type: ignore[misc]


def test_empty_registry_is_supported() -> None:
    registry = ExpectationRegistry()

    assert len(registry) == 0
    assert tuple(registry) == ()
    assert registry.get("unknown") is None


def test_registry_rejects_duplicate_set_identifiers() -> None:
    with pytest.raises(ValueError, match="doivent être uniques"):
        ExpectationRegistry((_set("same"), _set("same")))


def test_expectations_package_has_no_reasoning_or_ai_dependency() -> None:
    source = inspect.getsource(expectation_models) + inspect.getsource(
        expectation_registry
    )

    assert "tpstudio.reasoning" not in source
    assert "openai" not in source.lower()
