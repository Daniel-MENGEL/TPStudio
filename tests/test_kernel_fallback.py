from __future__ import annotations

from pathlib import Path

import nbformat
import pytest

import tpstudio.notebook_execution as execution_module
from tpstudio.notebook_execution import (
    execute_notebook_copy,
    resolve_kernel_selection,
)


def _notebook_with_kernel(name: str):
    notebook = nbformat.v4.new_notebook()
    notebook.metadata["kernelspec"] = {
        "name": name,
        "display_name": name,
        "language": "python",
    }
    return notebook


def test_resolve_kernel_uses_explicit_kernel_when_available() -> None:
    notebook = _notebook_with_kernel("conda-base-py")

    selection = resolve_kernel_selection(
        notebook,
        explicit_kernel_name="python3",
        available_kernels={"python3", "other"},
    )

    assert selection.declared_kernel == "conda-base-py"
    assert selection.used_kernel == "python3"
    assert selection.fallback_used is False


def test_resolve_kernel_uses_declared_kernel_when_available() -> None:
    notebook = _notebook_with_kernel("conda-base-py")

    selection = resolve_kernel_selection(
        notebook,
        available_kernels={"conda-base-py", "python3"},
    )

    assert selection.used_kernel == "conda-base-py"
    assert selection.fallback_used is False


def test_resolve_kernel_falls_back_to_python3() -> None:
    notebook = _notebook_with_kernel("conda-base-py")

    selection = resolve_kernel_selection(
        notebook,
        available_kernels={"python3"},
    )

    assert selection.declared_kernel == "conda-base-py"
    assert selection.used_kernel == "python3"
    assert selection.fallback_used is True


def test_resolve_kernel_rejects_missing_explicit_kernel() -> None:
    notebook = _notebook_with_kernel("conda-base-py")

    with pytest.raises(ValueError, match="Kernel demandé introuvable"):
        resolve_kernel_selection(
            notebook,
            explicit_kernel_name="kernel-inexistant",
            available_kernels={"python3"},
        )


def test_resolve_kernel_reports_available_kernels_when_no_fallback() -> None:
    notebook = _notebook_with_kernel("conda-base-py")

    with pytest.raises(RuntimeError, match="Kernels disponibles : julia"):
        resolve_kernel_selection(
            notebook,
            available_kernels={"julia"},
        )


def test_execute_notebook_copy_uses_automatic_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "copie.ipynb"
    output = tmp_path / "copie-executed.ipynb"

    notebook = _notebook_with_kernel("conda-base-py")
    notebook.cells = [nbformat.v4.new_code_cell("print('ok')")]
    nbformat.write(notebook, source)

    captured = {}

    class FakeClient:
        def __init__(self, notebook, **kwargs):
            self.notebook = notebook
            self.kwargs = kwargs
            captured.update(kwargs)

        def execute(self):
            cell = self.notebook.cells[0]
            self.kwargs["on_cell_start"](cell=cell, cell_index=0)
            cell.execution_count = 1
            cell.outputs = [
                nbformat.v4.new_output(
                    "stream",
                    name="stdout",
                    text="ok\n",
                )
            ]
            return self.notebook

    monkeypatch.setattr(
        execution_module,
        "_available_kernel_names",
        lambda: {"python3"},
    )
    monkeypatch.setattr(
        execution_module,
        "_load_execution_backend",
        lambda: (
            nbformat,
            FakeClient,
            (RuntimeError,),
        ),
    )

    result = execute_notebook_copy(source, output)

    assert captured["kernel_name"] == "python3"
    assert result.success is True
    assert result.declared_kernel == "conda-base-py"
    assert result.used_kernel == "python3"
    assert result.fallback_used is True
