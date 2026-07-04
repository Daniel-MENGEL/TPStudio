from __future__ import annotations

import json
from pathlib import Path

import nbformat
import pytest

import tpstudio.notebook_execution as execution_module
from tpstudio.notebook_execution import (
    execute_notebook_copy,
    format_execution_result,
)


class FakeCellExecutionError(Exception):
    pass


class FakeCellTimeoutError(Exception):
    pass


class FakeDeadKernelError(Exception):
    pass


def _backend(client_class):
    return (
        nbformat,
        client_class,
        (
            FakeCellExecutionError,
            FakeCellTimeoutError,
            FakeDeadKernelError,
        ),
    )


def _write_code_notebook(path: Path, source: str = "print('ok')") -> None:
    notebook = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_code_cell(source)]
    )
    nbformat.write(notebook, path)


def test_execute_notebook_copy_preserves_original_and_saves_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "copie.ipynb"
    output = tmp_path / "executions" / "copie-executed.ipynb"
    _write_code_notebook(source)

    original = source.read_text(encoding="utf-8")

    class FakeClient:
        def __init__(self, notebook, **kwargs):
            self.notebook = notebook
            self.kwargs = kwargs

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
        "_load_execution_backend",
        lambda: _backend(FakeClient),
    )

    result = execute_notebook_copy(source, output)

    assert result.success is True
    assert result.completed is True
    assert result.attempted_code_cells == 1
    assert result.total_code_cells == 1
    assert result.error_count == 0

    assert source.read_text(encoding="utf-8") == original
    assert output.exists()

    executed = nbformat.read(output, as_version=4)
    assert executed.cells[0].outputs[0].text == "ok\n"


def test_execute_notebook_copy_saves_partial_notebook_on_cell_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "copie.ipynb"
    output = tmp_path / "copie-executed.ipynb"
    _write_code_notebook(source, "1 / 0")

    class FailingClient:
        def __init__(self, notebook, **kwargs):
            self.notebook = notebook
            self.kwargs = kwargs

        def execute(self):
            cell = self.notebook.cells[0]
            self.kwargs["on_cell_start"](cell=cell, cell_index=0)
            cell.outputs = [
                nbformat.v4.new_output(
                    "error",
                    ename="ZeroDivisionError",
                    evalue="division by zero",
                    traceback=["Traceback", "ZeroDivisionError"],
                )
            ]
            self.kwargs["on_cell_error"](
                cell=cell,
                cell_index=0,
                execute_reply={},
            )
            raise FakeCellExecutionError("division by zero")

    monkeypatch.setattr(
        execution_module,
        "_load_execution_backend",
        lambda: _backend(FailingClient),
    )

    result = execute_notebook_copy(source, output)

    assert result.success is False
    assert result.completed is False
    assert result.error_count == 1
    assert result.failed_cell_index == 0
    assert result.error_type == "ZeroDivisionError"
    assert result.error_message == "division by zero"
    assert output.exists()

    executed = nbformat.read(output, as_version=4)
    assert executed.cells[0].outputs[0].output_type == "error"


def test_execute_notebook_copy_refuses_source_as_output(tmp_path: Path) -> None:
    source = tmp_path / "copie.ipynb"
    _write_code_notebook(source)

    with pytest.raises(ValueError, match="copie originale"):
        execute_notebook_copy(source, source)


def test_execute_notebook_copy_refuses_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "copie.ipynb"
    output = tmp_path / "copie-executed.ipynb"
    _write_code_notebook(source)
    output.write_text("à conserver", encoding="utf-8")

    with pytest.raises(FileExistsError, match="--overwrite"):
        execute_notebook_copy(source, output)


def test_format_execution_result_mentions_error() -> None:
    from tpstudio.notebook_execution import NotebookExecutionResult

    result = NotebookExecutionResult(
        source=Path("copie.ipynb"),
        output=Path("copie-executed.ipynb"),
        success=False,
        completed=False,
        attempted_code_cells=3,
        total_code_cells=5,
        error_count=1,
        failed_cell_index=2,
        error_type="ValueError",
        error_message="valeur invalide",
    )

    text = format_execution_result(result)

    assert "interrompue avec erreur" in text
    assert "3/5" in text
    assert "Première cellule en erreur : 3" in text
    assert "ValueError" in text
