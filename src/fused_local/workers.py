from functools import partial
import os
from typing import Awaitable, Callable, ParamSpec, TypeVar
import trio
import trio_parallel
from fused_local.user_code import next_code_reload, import_user_code, USER_CODE_PATH


def _worker_init():
    print(f"worker init {os.getpid()}")
    import_user_code(USER_CODE_PATH)


_WORKER_CTX: trio_parallel.WorkerContext | None = None
_WORKER_CTX_LOCK = trio.Lock()


async def _warmup_workers(
    ctx: trio_parallel.WorkerContext, limiter: trio.CapacityLimiter | None = None
) -> None:
    "Scale up the worker context to full size"
    if not limiter:
        limiter = trio_parallel.current_default_worker_limiter()

    async with trio.open_nursery() as nursery:
        for _ in range(limiter.total_tokens):  # type: ignore
            nursery.start_soon(partial(ctx.run_sync, cancellable=True), bool)  # type: ignore


async def manage_worker_pool(
    restart_on: Callable[[], Awaitable[object]], init: Callable[[], object] = bool
):
    """
    Long-running function to manage the worker process pool and code reloads.

    Parameters
    ----------
    restart_on:
        An async function that returns when the pool should be restarted.
    """
    global _WORKER_CTX
    async with _WORKER_CTX_LOCK:
        while True:
            assert _WORKER_CTX is None, _WORKER_CTX
            async with trio_parallel.open_worker_context(
                init=init,
                # worker_type=trio_parallel.WorkerType.FORKSERVER
            ) as worker_ctx:
                print("opened worker context")
                await _warmup_workers(worker_ctx)
                print("warmed up workers, waiting for reload")

                _WORKER_CTX = worker_ctx
                _WORKER_CTX_LOCK.release()
                # other code can now submit to the worker context
                try:
                    await restart_on()
                finally:
                    # try-finally is largely unnecessary, but it protects against the
                    # rare race condition where during overall shutdown, we've closed
                    # the worker context, but a `run_sync` (tile request) is submitted
                    # after that, which would raise a `trio.ClosedResourceError`.
                    await _WORKER_CTX_LOCK.acquire()
                    _WORKER_CTX = None

                print("code reloaded, shutting down workers")

            print("workers shut down")


P = ParamSpec("P")
R = TypeVar("R")


async def run_sync(func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """
    Run ``sync_fn(*args)`` in a separate process and return/raise its outcome.

    Cancellation in the parent process will send SIGKILL to the worker process.
    """
    async with _WORKER_CTX_LOCK:
        if not (ctx := _WORKER_CTX):
            raise trio.ClosedResourceError("No worker context available")

    # The lock is only for mutation of the `_WORKER_CTX` variable itself.
    # Don't hold it while the task is running; that way a code reload
    # can shut down the context and cancel this task.

    return await ctx.run_sync(partial(func, *args, **kwargs), cancellable=True)


if __name__ == "__main__":
    from fused_local.user_code import watch_reload_user_code

    async def main():
        try:
            async with trio.open_nursery() as nursery:
                nursery.start_soon(watch_reload_user_code, USER_CODE_PATH)
                nursery.start_soon(manage_worker_pool, next_code_reload, _worker_init)
        except* KeyboardInterrupt:
            print("shut down")

    trio.run(main)
