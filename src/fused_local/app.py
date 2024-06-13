from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
import textwrap
from typing import AsyncIterator
import webbrowser

import anyio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
import trio

from fused_local.config import config
from fused_local.lib import TileFunc, _initial_map_state
from fused_local.models import AppState, TileLayer
from fused_local.render import render_tile
from fused_local.user_code import (
    RepeatEvent,
    import_user_code,
    watch_with_event,
    reload_user_code,
)
from fused_local.workers import WorkerPool


FRONTEND_DIR = Path(__file__).parent / "frontend"
WORKER_POOL: WorkerPool | None = None

USER_CODE_CHANGED = RepeatEvent()
POOL_RESTARTED_AFTER_CODE_CHANGE = RepeatEvent()
FRONTEND_CODE_CHANGED = RepeatEvent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO is there a nicer way to get the user code path in here than a global variable?
    async with anyio.create_task_group() as tg:
        tg.start_soon(
            watch_with_event,
            config().user_code_path,
            USER_CODE_CHANGED,
            name="Code watcher",
        )
        tg.start_soon(
            watch_with_event,
            FRONTEND_DIR,
            FRONTEND_CODE_CHANGED,
            name="Frontend watcher",
        )

        global WORKER_POOL
        WORKER_POOL = WorkerPool(
            init=partial(import_user_code, config().user_code_path)
        )
        print(f"Launching pool of {WORKER_POOL.n_workers} workers...")
        async with WORKER_POOL:
            print("Workers running")

            async def reimport_on_code_reload():
                assert WORKER_POOL
                while True:
                    await USER_CODE_CHANGED.wait()
                    print("Code changed; re-importing on workers")
                    try:
                        # NOTE: for now, we just re-import without restarting worker
                        # processes, because it's so much faster. Ideally we might get a
                        # forkserver running well enough to make this quick, because
                        # it's unclear how well our hacky import process works with
                        # multiple files, imports, new dependencies, etc.
                        await WORKER_POOL.run_sync_all(
                            reload_user_code, config().user_code_path
                        )
                    except trio.ClosedResourceError:
                        return
                    POOL_RESTARTED_AFTER_CODE_CHANGE.reset()

            tg.start_soon(reimport_on_code_reload, name="Worker pool re-importer")

            print(f"Map is ready to go at {config().url}")

            if not config().dev:
                print(
                    "⚠️ Your browser may warn that the page is not trusted! Click through to visit the page anyway (you're just connecting to your own computer) ⚠️"
                )
                print("You can totally trust us right 😉")
                print(
                    textwrap.dedent("""
                        Technical detail: we serve map tiles over HTTP/2, because then your browser will request every tile in parallel.
                        With HTTP/1, your browser will only request 6 at a time---way slower!
                        However, HTTP/2 requires HTTPS, so we have to make a local self-signed certificate to encrypt the connection.
                        Because this is self-signed, your browser (correctly) warns you that it's not from a trusted certificate authority.
                        """)
                )

            if config().open_browser:
                webbrowser.open_new_tab(config().url)

            yield

            print("Shutting down...")
            tg.cancel_scope.cancel()


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
    assert WORKER_POOL
    print(f"tile request: {layer} {z} {x} {y} {vmin} {vmax} {cmap} {hash}")
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
        assert WORKER_POOL
        while True:
            # NOTE: we have to go to workers for this because we aren't actually
            # importing user code in the app for isolation reasons
            new_state = await WORKER_POOL.run_sync(_app_state_json)
            yield new_state
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
        await FRONTEND_CODE_CHANGED.wait()
        print("Frontend code changed; reloading")
        await websocket.close()
    except WebSocketDisconnect:
        pass


# https://stackoverflow.com/a/77823873
class StaticFilesNoCache(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


# Dynamically add routes for static files, depending on whether we're running in dev mode or not.
# Called in `serve.py`.
def setup_static_serving():
    if config().dev:

        @app.get("/")
        async def root():
            # - add HMR (cause we're HTTP/1.1, so websockets won't crash hyper)
            # - disable cache
            with open(FRONTEND_DIR / "index.html") as f:
                html = f.read()

            return HTMLResponse(
                html + "\n" + HMR,
                headers={
                    "Cache-Control": "no-cache",
                    "Expires": "0",
                },
            )

        app.mount(
            "/",
            StaticFilesNoCache(directory=FRONTEND_DIR, html=True),
            name="static",
        )
    else:
        app.mount(
            "/",
            StaticFiles(directory=FRONTEND_DIR, html=True),
            name="static",
        )


HMR = """
<script>
    (() => {
        const hmrPath = "/hmr"
        const socketUrl = (
            (window.location.protocol === "https:" ? "wss://" : "ws://")
            + window.location.host
            + hmrPath
        )
        // https://stackoverflow.com/a/68750487
        // const connect = () => { return new WebSocket(socketUrl, null, null, null, {rejectUnauthorized: false}) };
        const connect = () => { return new WebSocket(socketUrl) };
        var ws = connect();
        /*
        * Hot Module Reload
        */
        ws.addEventListener('close', () => {
            const interAttemptTimeoutMilliseconds = 500;
            const maxAttempts = 5;
            let attempts = 0;
            const reloadIfCanConnect = () => {
                console.log('[WS:info]', 'Attempting to reconnect to dev server...');
                attempts++;
                if (attempts > maxAttempts) {
                    console.error('[WS:error]', 'HMR could not reconnect to dev server.');
                    return;
                }
                socket = connect();
                socket.addEventListener('error', () => {
                    setTimeout(reloadIfCanConnect, interAttemptTimeoutMilliseconds);
                });
                socket.addEventListener('open', () => {
                    location.reload();
                });
            };
            reloadIfCanConnect();
        });
    })();
</script>
"""
