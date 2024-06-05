import io

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
from PIL import Image

import pydeck as pdk

app = FastAPI()


def generate_tile(z: int, x: int, y: int) -> Image.Image:
    # This is a placeholder function. Replace this with your actual tile generation logic.
    img = Image.new("RGB", (256, 256), color=(73, 109, 137))
    return img


@app.get("/", response_class=HTMLResponse)
async def root():
    # Set the viewport location
    view_state = pdk.ViewState(
        longitude=-1.415,
        latitude=52.2323,
        zoom=6,
        min_zoom=5,
        max_zoom=15,
        pitch=40.5,
        bearing=-27.36,
    )

    # Render
    r = pdk.Deck(layers=[], initial_view_state=view_state)
    html = r.to_html(notebook_display=False, as_string=True)

    return html


@app.get("/tiles/{z}/{x}/{y}.png")
async def tile(z: int, x: int, y: int):
    # Generate the tile
    img = generate_tile(z, x, y)

    # Save the image to a BytesIO object
    img_io = io.BytesIO()
    img.save(img_io, "PNG")
    img_io.seek(0)

    # Return the image as a streaming response
    return StreamingResponse(img_io, media_type="image/png")
