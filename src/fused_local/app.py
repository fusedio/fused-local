from pathlib import Path

import pydeck as pdk
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from fused_local.lib import TileFunc
from fused_local.render import render_tile
from fused_local.user_code import reloaded

app = FastAPI()

# HACK
# https://github.com/agressin/pydeck_myTileLayer
# won't need for long though
pdk.settings.custom_libraries = [
    {
        "libraryName": "MyTileLayerLibrary",
        "resourceUri": "https://cdn.jsdelivr.net/gh/agressin/pydeck_myTileLayer@master/dist/bundle.js",
    }
]


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

    names = tile_layers()
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
):
    # NOTE: with sync `def`, fastapi automatically runs in a threadpool
    png = render_tile(layer, z, x, y, vmin, vmax, cmap)
    return Response(png, media_type="image/png")


@app.get("/tiles")
def tile_layers() -> list[str]:
    return list(TileFunc._instances)

# ok wtf is going on
# every _other_ reload works
# something is fucked with the channel i think
# and the browser wants to open 2 websockets ?!
# so basically when we do a reload, we end up closing just 1 of the sockets
# which the browser wasn't actually listening to anymore?!
# the primary question is why the f doesn't `r.receive()` happen in both coroutines
@app.websocket("/hmr")
async def hmr_liveness(websocket: WebSocket):
    with reloaded.clone() as r:
        # https://paregis.me/posts/fastapi-frontend-development/
        try:
            await websocket.accept()
            print(f"accpeted {websocket}")
            await r.receive()  # todo how to clone
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

# put at end so that it doesn't shadow other routes
# https://stackoverflow.com/a/73916745
app.mount(
    "/",
    StaticFiles(directory=Path(__file__).parent / "frontend", html=True),
    name="static",
)
