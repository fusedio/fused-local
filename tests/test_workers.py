import os
import pytest
import trio.testing
from fused_local.workers import WorkerPool


@trio.testing.trio_test
async def test_worker_pool():
    pool = WorkerPool(2)

    with pytest.raises(trio.ClosedResourceError, match="Worker pool is closed"):
        await pool.run_sync(lambda: None)

    async with pool:
        first_pid = await pool.run_sync(os.getpid)
        assert first_pid != os.getpid()

        await pool.restart()

        second_pid = await pool.run_sync(os.getpid)
        assert second_pid != first_pid != os.getpid()

    with pytest.raises(trio.ClosedResourceError, match="Worker pool is closed"):
        await pool.run_sync(lambda: None)

    with pytest.raises(trio.ClosedResourceError, match="Worker pool is closed"):
        await pool.restart()
