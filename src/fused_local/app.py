from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import AsyncIterator

import anyio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import trio

from fused_local.lib import TileFunc, _initial_map_state
from fused_local.models import AppState, TileLayer
from fused_local.render import render_tile
from fused_local.user_code import (
    USER_CODE_PATH,
    RepeatEvent,
    import_user_code,
    watch_with_event,
    reload_user_code,
)
from fused_local.workers import WorkerPool


FRONTEND_DIR = Path(__file__).parent / "frontend"
WORKER_POOL = WorkerPool(init=partial(import_user_code, USER_CODE_PATH))

USER_CODE_CHANGED = RepeatEvent()
POOL_RESTARTED_AFTER_CODE_CHANGE = RepeatEvent()
FRONTEND_CODE_CHANGED = RepeatEvent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO is there a nicer way to get the user code path in here than a global variable?
    async with anyio.create_task_group() as tg:
        tg.start_soon(
            watch_with_event, USER_CODE_PATH, USER_CODE_CHANGED, name="Code watcher"
        )
        tg.start_soon(
            watch_with_event,
            FRONTEND_DIR,
            FRONTEND_CODE_CHANGED,
            name="Frontend watcher",
        )

        async with WORKER_POOL:
            print("started worker pool")

            async def reimport_on_code_reload():
                while True:
                    await USER_CODE_CHANGED.wait()
                    print("re-importing on worker pool")
                    try:
                        # NOTE: for now, we just re-import without restarting worker
                        # processes, because it's so much faster. Ideally we might get a
                        # forkserver running well enough to make this quick, because
                        # it's unclear how well our hacky import process works with
                        # multiple files, imports, new dependencies, etc.
                        await WORKER_POOL.run_sync_all(reload_user_code, USER_CODE_PATH)
                    except trio.ClosedResourceError:
                        print("not re-importing on pool")
                        return
                    POOL_RESTARTED_AFTER_CODE_CHANGE.reset()

            tg.start_soon(reimport_on_code_reload, name="Worker pool re-importer")

            yield

            print("cancelling file watch")
            tg.cancel_scope.cancel()

        print("closed worker pool")


app = FastAPI(lifespan=lifespan)


@app.get("/tiles/{layer}/{z}/{x}/{y}.png")
async def tile(
    layer: str,
    z: int,
    x: int,
    y: int,
    vmin: float,
    vmax: float,
    cmap: str | None = None,
    hash: str | None = None,
    # TODO should `hash` be part of the URL path? It's basically a 'version', and in the
    # future, maybe versions would be explicit. For now, it's used just to make deck.gl
    # reload a tile when the user code changes, by changing the URL.
):
    png = await WORKER_POOL.run_sync(
        render_tile, layer, z, x, y, vmin, vmax, cmap, hash
    )
    return Response(png, media_type="image/png")


def _app_state_json() -> str:
    return AppState(
        layers=[
            TileLayer(
                name=t.name,
                hash=t.hash,
                # TODO don't hardcode these
                min_zoom=6,
                max_zoom=16,
                vmin=0,
                vmax=6000,
                visible=True,
            )
            for t in TileFunc._instances.values()
        ],
        initial_map_state=_initial_map_state(),
    ).model_dump_json()


@app.get("/app_state")
async def app_state():
    async def _app_state_generator() -> AsyncIterator[str]:
        while True:
            # NOTE: we have to go to workers for this because we aren't actually
            # importing user code in the app for isolation reasons
            print("new code")
            new_state = await WORKER_POOL.run_sync(_app_state_json)
            print("sending sse reload")
            yield new_state
            print("sent sse reload")
            # NOTE: if we just waited for `USER_CODE_CHANGED`, there's a race condition
            # between the pool restarting and getting the new state. We might get state
            # from the pool before it's restarted.
            await POOL_RESTARTED_AFTER_CODE_CHANGE.wait()

    return EventSourceResponse(_app_state_generator())


@app.websocket("/hmr")
async def hmr_liveness(websocket: WebSocket):
    # https://paregis.me/posts/fastapi-frontend-development/
    try:
        await websocket.accept()
        print(f"accepted {websocket}")
        await FRONTEND_CODE_CHANGED.wait()
        print(f"closing websocket {websocket}")
        await websocket.close()
        print(f"closed {websocket}")
    except WebSocketDisconnect:
        pass


# https://stackoverflow.com/a/77823873
class StaticFilesNoCache(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


# put at end so that it doesn't shadow other routes
# https://stackoverflow.com/a/73916745
app.mount(
    "/",
    StaticFilesNoCache(directory=FRONTEND_DIR, html=True),
    name="static",
)
