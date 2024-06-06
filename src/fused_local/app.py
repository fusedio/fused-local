import pydeck as pdk
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from odc.geo import XY
from odc.geo.gridspec import GridSpec

from fused_local.lib import TileFunc
from fused_local.render import to_png

from fused_local import example

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


@app.get("/", response_class=HTMLResponse)
async def root():
    view_state = pdk.ViewState(
        longitude=-105.78,
        latitude=35.79,
        zoom=9,
        min_zoom=5,
        max_zoom=15,
        debounce_time=100,  # ms
    )

    print(list(TileFunc._instances))
    layers = [
        pdk.Layer(
            type="MyTileLayer",  # see hack above
            data=f"/tiles/{name}" + "/{z}/{x}/{y}.png?vmin=0&vmax=8000",
            min_zoom=5,
        )
        for name in TileFunc._instances.keys()
    ]

    # Render
    r = pdk.Deck(layers=layers, initial_view_state=view_state)
    html = r.to_html(notebook_display=False, as_string=True)

    return html


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
    try:
        func = TileFunc._instances[layer]
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"Tile layer {layer!r} does not exist"
        )

    # 512px seems to give better resolution. not sure what's going on here yet.
    gbox = GridSpec.web_tiles(z, npix=512).tile_geobox(XY(x, y))  # cache?

    result = func(gbox)

    png = to_png(result, range=(vmin, vmax), cmap=cmap)

    return Response(png, media_type="image/png")


@app.get("/tiles")
def tile_layers():
    return list(TileFunc._instances.keys())
