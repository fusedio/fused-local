import os
from functools import partial
from typing import Callable, ParamSpec, TypeVar

import trio
import trio_parallel
from trio_parallel._impl import DEFAULT_CONTEXT, DEFAULT_LIMIT, WorkerType

P = ParamSpec("P")
R = TypeVar("R")


class WorkerPool:
    _ctx: trio_parallel.WorkerContext | None
    _ctx_lock: trio.Lock
    _limiter: trio.CapacityLimiter

    _n_workers: int
    _idle_timeout: float
    _init: Callable[[], object]
    _retire: Callable[[], bool]
    _grace_period: float
    _worker_type: WorkerType

    def __init__(
        self,
        n_workers: int = DEFAULT_LIMIT,
        idle_timeout: float = DEFAULT_CONTEXT.idle_timeout,
        init: Callable[[], object] = DEFAULT_CONTEXT.init,
        retire: Callable[[], bool] = DEFAULT_CONTEXT.retire,
        grace_period: float = DEFAULT_CONTEXT.grace_period,
        worker_type: WorkerType = WorkerType.SPAWN,  # type: ignore
    ) -> None:
        self._ctx = None
        self._ctx_lock = trio.Lock()
        self._limiter = trio.CapacityLimiter(n_workers)

        self._idle_timeout = idle_timeout
        self._init = init
        self._retire = retire
        self._grace_period = grace_period
        self._worker_type = worker_type

    async def __aenter__(self):
        async with self._ctx_lock:
            await self._start()
        return self

    async def __aexit__(self, *exc_info):
        async with self._ctx_lock:
            await self._stop()

    async def _start(self) -> None:
        # assumes lock is held
        assert self._ctx is None, self._ctx

        # TODO don't use internal API
        self._ctx = trio_parallel.WorkerContext._create(
            self._idle_timeout,
            self._init,
            self._retire,
            self._grace_period,
            self._worker_type,
        )

        print("opened worker context")
        await self._scale()
        print("scaled up workers")

    async def _stop(self) -> None:
        # assumes lock is held
        if self._ctx is None:
            return

        print("closing worker context")
        await self._ctx._aclose()
        self._ctx = None
        print("closed worker context")

    async def _scale(self) -> None:
        # assumes lock is held
        assert (ctx := self._ctx), "Worker pool is closed"
        async with trio.open_nursery() as nursery:
            for _ in range(self.n_workers):
                nursery.start_soon(
                    partial(ctx.run_sync, cancellable=True, limiter=self._limiter),  # type: ignore
                    bool,
                )

    async def restart(self):
        async with self._ctx_lock:
            if not self._ctx:
                raise trio.ClosedResourceError("Worker pool is closed")

            await self._stop()
            await self._start()

    async def run_sync(
        self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        """
        Run ``sync_fn(*args)`` in a separate process and return/raise its outcome.

        Cancellation in the parent process will send SIGKILL to the worker process.
        """
        async with self._ctx_lock:
            # The lock is only for mutation of the `_ctx` variable itself. Don't hold it
            # while the task is running; that way a concurrent restart/shutdown can shut
            # down the current pool and cancel this task.
            if not (ctx := self._ctx):
                raise trio.ClosedResourceError("Worker pool is closed")

        return await ctx.run_sync(partial(func, *args, **kwargs), cancellable=True)

    async def run_sync_all(
        self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        "Convenience to run ``sync_fn(*args)`` on all workers"
        async with trio.open_nursery() as nursery:
            for _ in range(self.n_workers):
                nursery.start_soon(partial(self.run_sync, func, *args, **kwargs))

    @property
    def n_workers(self) -> int:
        return self._limiter.total_tokens  # type: ignore


if __name__ == "__main__":
    from fused_local.user_code import (
        USER_CODE_PATH,
        import_user_code,
        watch_with_event,
        RepeatEvent,
    )

    def _worker_init():
        print(f"worker init {os.getpid()}")
        import_user_code(USER_CODE_PATH)

    USER_CODE_CHANGED = RepeatEvent()

    async def main():
        try:
            async with trio.open_nursery() as nursery:
                async with WorkerPool(2, init=_worker_init) as pool:
                    nursery.start_soon(
                        watch_with_event, USER_CODE_PATH, USER_CODE_CHANGED
                    )

                    async def submit_loop():
                        while True:
                            async with trio.open_nursery() as nursery:
                                for _ in range(pool.n_workers):
                                    nursery.start_soon(
                                        pool.run_sync,
                                        (
                                            lambda: print(
                                                f"hello from worker {os.getpid()}"
                                            )
                                        ),
                                    )

                            await trio.sleep(0.5)

                    nursery.start_soon(submit_loop)

                    while True:
                        await USER_CODE_CHANGED.wait()
                        print("restarting worker pool")
                        await pool.restart()
                        print("restarted worker pool")

        except* KeyboardInterrupt:
            print("shut down")

    trio.run(main)
