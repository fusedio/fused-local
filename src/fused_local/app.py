from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import anyio
import pydeck as pdk
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from fused_local.lib import TileFunc, _initial_map_state
from fused_local.models import AppState, TileLayer
from fused_local.render import render_tile
from fused_local.user_code import (
    USER_CODE_PATH,
    next_code_reload,
    next_frontend_reload,
    watch_for_frontend_reload,
    watch_reload_user_code,
)

# HACK
# https://github.com/agressin/pydeck_myTileLayer
# won't need for long though
pdk.settings.custom_libraries = [
    {
        "libraryName": "MyTileLayerLibrary",
        "resourceUri": "https://cdn.jsdelivr.net/gh/agressin/pydeck_myTileLayer@master/dist/bundle.js",
    }
]

FRONTEND_DIR = Path(__file__).parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO allow passing in file as CLI argument.
    # uvcorn/gunicorn won't accept extraneous arguments, so easier to hardcode for prototype.

    async with anyio.create_task_group() as tg:
        print(f"watching {USER_CODE_PATH}")
        print(f"watching {FRONTEND_DIR}")
        tg.start_soon(watch_reload_user_code, USER_CODE_PATH, name="Code watcher")
        tg.start_soon(watch_for_frontend_reload, FRONTEND_DIR, name="Frontend watcher")
        yield
        print("cancelling file watch")
        tg.cancel_scope.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/map", response_class=HTMLResponse)
async def root():
    view_state = pdk.ViewState(
        longitude=-105.78,
        latitude=35.79,
        zoom=9,
        min_zoom=5,
        max_zoom=15,
        debounce_time=100,  # ms
    )

    names = list(TileFunc._instances)
    print(names)
    layers = [
        pdk.Layer(
            type="MyTileLayer",  # see hack above
            data=f"/tiles/{name}" + "/{z}/{x}/{y}.png?vmin=0&vmax=8000",
            min_zoom=5,
        )
        for name in names
    ]

    # Render
    r = pdk.Deck(layers=layers, initial_view_state=view_state)
    html = r.to_html(notebook_display=False, as_string=True)
    assert isinstance(html, str)

    return html + "\n" + HMR_SCRIPT


@app.get("/tiles/{layer}/{z}/{x}/{y}.png")
def tile(
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
    # NOTE: with sync `def`, fastapi automatically runs in a threadpool
    png = render_tile(layer, z, x, y, vmin, vmax, cmap, hash)
    return Response(png, media_type="image/png")


def _app_state() -> AppState:
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
    )


@app.get("/app_state")
async def app_state():
    async def _app_state_generator() -> AsyncIterator[str]:
        while True:
            print("sending sse reload")
            yield _app_state().model_dump_json()
            await next_code_reload()

    return EventSourceResponse(_app_state_generator())


@app.websocket("/hmr")
async def hmr_liveness(websocket: WebSocket):
    # https://paregis.me/posts/fastapi-frontend-development/
    try:
        await websocket.accept()
        print(f"accepted {websocket}")
        await next_frontend_reload()
        print(f"closing websocket {websocket}")
        await websocket.close()
        print(f"closed {websocket}")
    except WebSocketDisconnect:
        pass


# https://paregis.me/posts/fastapi-frontend-development/
HMR_SCRIPT = """
<script>
(() => {
    const socketUrl = "ws://127.0.0.1:8000/hmr";
    // https://stackoverflow.com/a/68750487
    // const connect = () => { return new WebSocket(socketUrl, null, null, null, {rejectUnauthorized: false}) };
    const connect = () => { return new WebSocket(socketUrl) };
    var ws = connect();
    /*
    * Hot Module Reload
    */
    ws.addEventListener('close',() => {
        const interAttemptTimeoutMilliseconds = 500;
        const maxAttempts = 5;
        let attempts = 0;
        const reloadIfCanConnect = () => {
            console.log('[WS:info]', 'Attempting to reconnect to dev server...');
            attempts++ ;
            if(attempts > maxAttempts){
                console.error('[WS:error]', 'HMR could not reconnect to dev server.');
                return;
            }
            socket = connect();
            socket.addEventListener('error',()=>{
                setTimeout(reloadIfCanConnect,interAttemptTimeoutMilliseconds);
            });
            socket.addEventListener('open',() => {
                location.reload();
            });
        };
        reloadIfCanConnect();
    });
})();
</script>
"""


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
