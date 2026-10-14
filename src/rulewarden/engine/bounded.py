"""Hard wall-clock bound for an evaluation: run it in a forked child and kill it on overrun (P5)."""

from __future__ import annotations

import os
import pickle
import select
import signal
import time
from collections.abc import Callable
from typing import TypeVar

from rulewarden.errors import BudgetExceeded, EngineError

T = TypeVar("T")


def run_bounded(fn: Callable[[], T], budget_s: float | None) -> T:
    """Call fn in a forked child with a deadline; returns its result or raises.

    BudgetExceeded on timeout; EngineError if the child crashes. With budget_s None
    (or on platforms without fork) fn runs in-process, which unit tests use.
    """
    if budget_s is None or not hasattr(os, "fork"):
        return fn()
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:  # pragma: no cover - exercised in a child process
        os.close(r)
        code = 0
        try:
            payload = pickle.dumps(("ok", fn()))
        except BaseException as exc:  # noqa: BLE001 - anything in the child must be reported
            payload = pickle.dumps(("err", f"{type(exc).__name__}: {exc}"))
            code = 1
        view = memoryview(payload)
        while view:
            n = os.write(w, view)
            view = view[n:]
        os.close(w)
        os._exit(code)
    os.close(w)
    chunks: list[bytes] = []
    deadline = time.monotonic() + budget_s
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                os.kill(pid, signal.SIGKILL)
                raise BudgetExceeded(f"evaluation exceeded its {budget_s:g}s budget and was killed")
            ready, _, _ = select.select([r], [], [], remaining)
            if not ready:
                continue
            chunk = os.read(r, 1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(r)
        _, status = os.waitpid(pid, 0)
    data = b"".join(chunks)
    if not data:
        raise EngineError(f"evaluation process died (status {status})")
    kind, value = pickle.loads(data)
    if kind == "err":
        raise EngineError(str(value))
    result: T = value
    return result
