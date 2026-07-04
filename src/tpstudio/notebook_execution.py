from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid


@dataclass(frozen=True)
class KernelSelection:
    declared_kernel: str
    used_kernel: str
    fallback_used: bool


@dataclass(frozen=True)
class NotebookExecutionResult:
    source: Path
    output: Path
    success: bool
    completed: bool
    attempted_code_cells: int
    total_code_cells: int
    error_count: int = 0
    failed_cell_index: int | None = None
    error_type: str = ""
    error_message: str = ""
    declared_kernel: str = ""
    used_kernel: str = ""
    fallback_used: bool = False


def execute_notebook_copy(
    source_path: str | Path,
    output_path: str | Path,
    *,
    cell_timeout: int = 60,
    kernel_name: str | None = None,
    continue_on_error: bool = False,
    overwrite: bool = False,
) -> NotebookExecutionResult:
    """Execute a notebook copy without ever modifying the source notebook."""

    source = Path(source_path)
    output = Path(output_path)

    _validate_source(source)
    _validate_output(source, output, overwrite=overwrite)

    if cell_timeout <= 0:
        raise ValueError("Le timeout par cellule doit être strictement positif.")

    nbformat, notebook_client_class, execution_exceptions = _load_execution_backend()
    notebook = nbformat.read(source, as_version=4)

    kernel_selection = resolve_kernel_selection(
        notebook,
        explicit_kernel_name=kernel_name,
    )

    total_code_cells = sum(
        1
        for cell in notebook.cells
        if getattr(cell, "cell_type", "") == "code"
    )

    attempted_indices: set[int] = set()
    failed_cell_index: int | None = None
    caught_exception: BaseException | None = None

    def on_cell_start(*, cell: Any, cell_index: int, **_: Any) -> None:
        if getattr(cell, "cell_type", "") == "code":
            attempted_indices.add(cell_index)

    def on_cell_error(
        *,
        cell: Any,
        cell_index: int,
        execute_reply: dict[str, Any],
        **_: Any,
    ) -> None:
        nonlocal failed_cell_index
        if failed_cell_index is None:
            failed_cell_index = cell_index

    client_kwargs: dict[str, Any] = {
        "timeout": cell_timeout,
        "allow_errors": continue_on_error,
        "resources": {"metadata": {"path": str(source.parent)}},
        "on_cell_start": on_cell_start,
        "on_cell_error": on_cell_error,
        "store_widget_state": True,
        "kernel_name": kernel_selection.used_kernel,
    }

    client = notebook_client_class(notebook, **client_kwargs)

    try:
        client.execute()
    except execution_exceptions as error:
        caught_exception = error
    except Exception as error:
        # Kernel startup/configuration failures are execution failures too.
        caught_exception = error

    error_outputs = _collect_error_outputs(notebook)

    if failed_cell_index is None and error_outputs:
        failed_cell_index = error_outputs[0][0]

    error_type = ""
    error_message = ""

    if error_outputs:
        _, first_error = error_outputs[0]
        error_type = str(first_error.get("ename", "") or "")
        error_message = str(first_error.get("evalue", "") or "")
    elif caught_exception is not None:
        error_type = type(caught_exception).__name__
        error_message = str(caught_exception)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(
        f".{output.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        nbformat.write(notebook, temporary_output)
        temporary_output.replace(output)
    finally:
        temporary_output.unlink(missing_ok=True)

    completed = caught_exception is None
    success = completed and not error_outputs

    return NotebookExecutionResult(
        source=source,
        output=output,
        success=success,
        completed=completed,
        attempted_code_cells=len(attempted_indices),
        total_code_cells=total_code_cells,
        error_count=len(error_outputs),
        failed_cell_index=failed_cell_index,
        error_type=error_type,
        error_message=error_message,
        declared_kernel=kernel_selection.declared_kernel,
        used_kernel=kernel_selection.used_kernel,
        fallback_used=kernel_selection.fallback_used,
    )


def resolve_kernel_selection(
    notebook: Any,
    *,
    explicit_kernel_name: str | None = None,
    available_kernels: set[str] | None = None,
) -> KernelSelection:
    declared_kernel = _declared_kernel_name(notebook)
    available = (
        set(available_kernels)
        if available_kernels is not None
        else _available_kernel_names()
    )

    if explicit_kernel_name:
        if explicit_kernel_name not in available:
            raise ValueError(
                _format_missing_kernel_message(
                    requested=explicit_kernel_name,
                    available=available,
                    explicit=True,
                )
            )

        return KernelSelection(
            declared_kernel=declared_kernel,
            used_kernel=explicit_kernel_name,
            fallback_used=False,
        )

    if declared_kernel and declared_kernel in available:
        return KernelSelection(
            declared_kernel=declared_kernel,
            used_kernel=declared_kernel,
            fallback_used=False,
        )

    if "python3" in available:
        return KernelSelection(
            declared_kernel=declared_kernel,
            used_kernel="python3",
            fallback_used=bool(
                declared_kernel
                and declared_kernel != "python3"
            ),
        )

    requested = declared_kernel or "(aucun kernel déclaré)"
    raise RuntimeError(
        _format_missing_kernel_message(
            requested=requested,
            available=available,
            explicit=False,
        )
    )


def format_execution_result(result: NotebookExecutionResult) -> str:
    if result.success:
        status = "succès"
    elif result.completed:
        status = "terminée avec erreurs"
    else:
        status = "interrompue avec erreur"

    lines = [
        "Exécution TPStudio",
        f"Statut : {status}",
    ]

    if result.declared_kernel:
        lines.append(
            f"Kernel déclaré par le notebook : {result.declared_kernel}"
        )
    else:
        lines.append("Kernel déclaré par le notebook : aucun")

    if result.used_kernel:
        lines.append(f"Kernel utilisé : {result.used_kernel}")

    lines.append(
        "Fallback automatique : "
        + ("oui" if result.fallback_used else "non")
    )

    lines.extend(
        [
            (
                "Cellules code tentées : "
                f"{result.attempted_code_cells}/{result.total_code_cells}"
            ),
            f"Erreurs détectées : {result.error_count}",
            f"Notebook exécuté : {result.output}",
        ]
    )

    if result.failed_cell_index is not None:
        lines.append(
            f"Première cellule en erreur : {result.failed_cell_index + 1}"
        )

    if result.error_type:
        lines.append(f"Type d'erreur : {result.error_type}")

    if result.error_message:
        lines.append(f"Message : {result.error_message}")

    return "\n".join(lines)


def _declared_kernel_name(notebook: Any) -> str:
    metadata = getattr(notebook, "metadata", {})
    kernelspec = metadata.get("kernelspec", {})
    return str(kernelspec.get("name", "") or "").strip()


def _available_kernel_names() -> set[str]:
    try:
        from jupyter_client.kernelspec import KernelSpecManager
    except ImportError as error:
        raise RuntimeError(
            "Impossible de lister les kernels Jupyter disponibles : "
            "jupyter_client est introuvable."
        ) from error

    try:
        specs = KernelSpecManager().find_kernel_specs()
    except Exception as error:
        raise RuntimeError(
            "Impossible de lister les kernels Jupyter disponibles."
        ) from error

    return set(specs)


def _format_missing_kernel_message(
    *,
    requested: str,
    available: set[str],
    explicit: bool,
) -> str:
    available_text = (
        ", ".join(sorted(available))
        if available
        else "aucun"
    )

    if explicit:
        return (
            f"Kernel demandé introuvable : {requested}. "
            f"Kernels disponibles : {available_text}."
        )

    return (
        f"Kernel du notebook indisponible : {requested}. "
        "Aucun fallback automatique vers python3 n'est possible. "
        f"Kernels disponibles : {available_text}."
    )


def _collect_error_outputs(notebook: Any) -> list[tuple[int, dict[str, Any]]]:
    errors: list[tuple[int, dict[str, Any]]] = []

    for cell_index, cell in enumerate(notebook.cells):
        if getattr(cell, "cell_type", "") != "code":
            continue

        for output in getattr(cell, "outputs", []):
            if getattr(output, "output_type", None) == "error":
                errors.append(
                    (
                        cell_index,
                        {
                            "ename": getattr(output, "ename", ""),
                            "evalue": getattr(output, "evalue", ""),
                        },
                    )
                )

    return errors


def _validate_source(source: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Copie introuvable : {source}")

    if not source.is_file():
        raise ValueError(f"Copie invalide : {source}")

    if source.suffix.lower() != ".ipynb":
        raise ValueError(f"Copie attendue au format .ipynb : {source}")


def _validate_output(
    source: Path,
    output: Path,
    *,
    overwrite: bool,
) -> None:
    if source.resolve() == output.resolve():
        raise ValueError(
            "Le notebook exécuté doit être écrit dans un autre fichier "
            "que la copie originale."
        )

    if output.exists() and not overwrite:
        raise FileExistsError(
            f"Sortie déjà existante : {output.name}. "
            "Utilise --overwrite pour la remplacer."
        )


def _load_execution_backend():
    try:
        import nbformat
        from nbclient import NotebookClient
        from nbclient.exceptions import (
            CellExecutionError,
            CellTimeoutError,
            DeadKernelError,
        )
    except ImportError as error:
        raise RuntimeError(
            "L'exécution des notebooks nécessite nbformat et nbclient."
        ) from error

    return (
        nbformat,
        NotebookClient,
        (CellExecutionError, CellTimeoutError, DeadKernelError),
    )
