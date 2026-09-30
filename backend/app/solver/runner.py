"""Outer circuit breaker around the solver, used by the API.

Layer 1 (cpsat.solve): CP-SAT deadline, pool and alternative clamps -> always returns.
Layer 2 (this module): the solve runs in a separate process. If it has not answered
  within hard_timeout the process is killed, so a stuck native call can never hang the
  API. A semaphore caps concurrent solves so a burst of requests cannot exhaust the CPU.
Layer 3 (frontend): fetch with AbortController timeout; the UI shows the Swedish message.
"""
import asyncio
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

from .cpsat import MAX_TIME_S, MESSAGES, solve
from .types import Card, Requirement, Solution, SolveOptions

MAX_CONCURRENT = 2
GRACE_S = 10.0  # model building + process start-up on top of the CP-SAT deadline

_sem = asyncio.Semaphore(MAX_CONCURRENT)
_pool: ProcessPoolExecutor | None = None


def _executor() -> ProcessPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ProcessPoolExecutor(max_workers=MAX_CONCURRENT,
                                    mp_context=mp.get_context("spawn"))
    return _pool


def _reset_executor():
    """Kill all workers (the only way to stop a running native solve)."""
    global _pool
    if _pool is not None:
        for proc in list(getattr(_pool, "_processes", {}).values()):
            proc.kill()
        _pool.shutdown(wait=False, cancel_futures=True)
    _pool = None


def _timeout_solution(msg: str) -> list[Solution]:
    return [Solution(status="UNKNOWN", message=msg)]


async def solve_guarded(cards: list[Card], reqs: list[Requirement],
                        opt: SolveOptions) -> list[Solution]:
    hard_timeout = min(opt.time_limit_s, MAX_TIME_S) + GRACE_S
    async with _sem:
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(_executor(), solve, cards, reqs, opt)
        try:
            return await asyncio.wait_for(fut, hard_timeout)
        except asyncio.TimeoutError:
            _reset_executor()
            return _timeout_solution(MESSAGES["UNKNOWN"] + " (avbruten av tidsgräns)")
        except BrokenProcessPool:
            _reset_executor()
            return _timeout_solution("Lösaren kraschade och startades om. Försök igen.")
