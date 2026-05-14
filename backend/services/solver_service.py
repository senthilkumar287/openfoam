"""
services/solver_service.py

Thin service wrapper around the OpenFOAM subprocess execution layer.
Keeps solver concerns out of both app.py (routing) and case_service.py
(file generation).

Public API
----------
    SolverService.run_blockmesh(runner, timeout)
    SolverService.run_solver(runner, solver_type, params, timeout)
    SolverService.run_sync(runner, solver_type, params, timeout)
    SolverService.run_async(runner, solver_type, params)
"""
from __future__ import annotations
import threading

from services.case_service import build_case, SOLVER_APPS


class SolverService:

    @staticmethod
    def build(runner, solver_type: str, params: dict) -> list[str]:
        """Write all case files via DictionaryService → Dictionary Engine."""
        written = build_case(runner.case_dir, solver_type, params)
        runner._params = dict(params)
        runner._params["solver_type"] = solver_type
        return written

    @staticmethod
    def run_blockmesh(runner, timeout: int = 60) -> None:
        """Delegate to runner's existing _run_blockmesh (subprocess logic unchanged)."""
        runner._run_blockmesh(timeout=timeout)

    @staticmethod
    def run_solver(runner, solver_type: str, params: dict, timeout: int = 600) -> None:
        """Delegate to runner's existing _run_solver (subprocess logic unchanged)."""
        runner._run_solver(solver_type, params, timeout=timeout)

    @staticmethod
    def run_sync(runner, solver_type: str, params: dict, timeout: int = 600) -> None:
        """Build case files then execute synchronously."""
        SolverService.build(runner, solver_type, params)
        SolverService.run_blockmesh(runner)
        SolverService.run_solver(runner, solver_type, params, timeout=timeout)

    @staticmethod
    def run_async(runner, solver_type: str, params: dict) -> None:
        """Build case files then execute in a background thread."""
        def _go():
            try:
                SolverService.build(runner, solver_type, params)
                SolverService.run_blockmesh(runner)
                SolverService.run_solver(runner, solver_type, params)
            except Exception as exc:
                runner.status    = "error"
                runner.error_msg = str(exc)

        t = threading.Thread(target=_go, daemon=True)
        runner._thread = t
        t.start()
