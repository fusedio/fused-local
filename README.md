# fused-local

🌎 Code to map. Instantly. 🌎

_Now on your own computer!_

![fused-local demo](media/fused-local-demo.gif)

You write geospatial analysis code using the tools you already know, `fused-local` lets you visualize that on an interactive map.

## Installation

```
pip install 'git+ssh://git@github.com/gjoseph92/fused-local.git'
```

## Example

```python
# example.py
import numpy as np
import pystac
import xarray as xr
import odc.stac
from odc.geo.geobox import GeoBox

import fused_local

fused_local.configure_map(
    title="Sentinel-2 demo",
    center="ski santa fe, nm",
    zoom=10,
)

@fused_local.tile
def s2_scene_june(gbox: GeoBox) -> xr.Dataset:
    item = pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_13SDV_20240601_0_L2A"
    )
    data = odc.stac.load([item], ["red", "green", "blue"], geobox=gbox)
    print(f"loaded data")
    # idk why odc.stac doesn't handle nodata / offer an option to mask it
    data = data.where(data != 0, np.nan)
    return data


# @fused_local.tile
# def s2_scene_march(gbox: GeoBox) -> xr.Dataset:
#     item = pystac.Item.from_file(
#         "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_13SDV_20240301_0_L2A"
#     )
#     data = odc.stac.load([item], ["red", "green", "blue"], geobox=gbox)
#     data = data.where(data != 0, np.nan)
#     return data


# @fused_local.tile
# def s2_composite(gbox: GeoBox) -> xr.Dataset:
#     client = pystac_client.Client.open("https://earth-search.aws.element84.com/v1")

#     items = client.search(
#         collections=["sentinel-2-l2a"],
#         bbox=tuple(gbox.geographic_extent.boundingbox),
#         datetime="2022-03-01/2022-04-01",
#         query={"eo:cloud_cover": {"lt": 10}},
#         max_items=20,
#     ).item_collection()

#     print(f"{len(items)=}")

#     stack = odc.stac.load(
#         items,
#         groupby="solar_day",
#         geobox=gbox,
#         bands=["red", "green", "blue"],
#         chunks={"time": 1},
#     )
#     stack = stack.isel(time=slice(4))
#     stack = stack.where(stack != 0, np.nan)
#     comp = stack.median("time")

#     return comp.compute()
```

Run fused-local on your file to open a map in your browser. Put the browser window and your code editor next to each other.

```
$ fused-local example.py
```

_Note: the first time the page opens, the browser will tell you it's unsafe. Click through this, you're just connecting to your own computer. We're serving over HTTPS so that we can use HTTP/2 for more parallelism, which requires generating a self-signed certificate. This is terrible UX and hopefully can be improved some day somehow._

Try un-commenting the other functions to see what happens.

The last one (`s2_composite`) is a lot slower, because it's potentially loading and compositing ~10 GeoTIFFs for each tile on the map!

But it also works anywhere in the world. (The first two are requesting one specific Sentinel-2 image captured over New Mexico, so they won't show data elsewhere.)

Try changing the `center=` argument in `configure_map` at the top to anywhere else you're curious about, then save the file.

## Usage

You write functions that take a [`GeoBox`](https://odc-geo.readthedocs.io/en/latest/intro-geobox.html) argument, and decorate them with `@fused_local.tile`:

```python
@fused_local.tile
def tile_function(gbox: GeoBox):
    # use GeoBox to search, clip, etc. the data
    ...
    return data # xarray Dataset, DataArray, NumPy array
```

`fused-local` will call your function in parallel many times with different `GeoBox`es. As you pan/zoom the map, each 512x512px tile on the map will end up being a `GeoBox` your function is called with.

The `GeoBox` defines the spatial area your function should run over, as well as the coordinate reference system, resolution, etc. You should use it as the bounding box when searching for data, as the resolution when loading it, and so on.

When you run `fused-local <your-script.py>`, this launches a pool of worker processes to run your code in parallel, and opens a map in the browser.

Every time you save the file, the map will update. (It may take a bit for the new tiles to show up, since they're computing.)

By default, outputs of your tile functions are cached (in a `cache/` directory in your current directory), up to 1GB. It can also be good to cache specific parts of your code as you experiment, too. Use `@fused_local.cache` for this.

Because you just installed `fused-local` in your project (hopefully in a virtualenv!), you can use whatever dependencies you want. `fused-local` is just running your code for you.

## Caveats / broken things

They are many. This is an extremely alpha prototype.

- Splitting your code across multiple files probably doesn't work.
- The auto-reload detection probably can't tell if things you've imported have changed.
- Caching is brittle.
- Caching sometimes seems to lock up; `rm -r cache` if things are weird.
- Requests aren't cancelled, so if you pan around fast, requests for tiles you're not looking at will keep running and stacking up and block new ones.
- No idea if work is well-distributed to worker processes.
- Worker processes aren't restarted if they die.
- No vector support yet.
- Probably hard to debug errors in your code. Everything about printing, logging, etc.
- Multiple outputs from one function not supported yet (coming soon).
- Generally configuring layers/the map from code.
- Progress indication, invalidating old tiles, etc.
- The dependencies are _insane_. There's a lot to pare down.

## Developing

### Python

1. Install [rye](https://rye.astral.sh) for managing Python and dependencies.
1. Clone the repo and `cd` into it
1. `rye sync` to create the virtual environment and install all dependencies.
1. `source .venv/bin/activate` to activate the virtual environment.

### ES

You could install Node and NPM however you like. This project uses [Volta](https://volta.sh) to manage the versions of these tools. If you have Volta installed, the Node and NPM versions are pinned in `package.json`, so running `node` in this directory will automatically install and use the correct version.

1. `npm install`
1. `npm run build` to compile into `src/fused_local/frontend`
1. `npm run build:watch` to rebuild on changes

### Python -> ES

The Pydantic models are automatically translated into equivalent TypeScript interfaces. It ain't Protobuf, but it's better than keeping two definitions in sync manually.

The TypeScript (in `js/generated`) can be generated by `rye run build_ts`. This is automatically run as part of `npm run build`.

### Typical dev process

1. In one terminal, start `npm run build:watch`.
1. In another, run `fused-local --dev example.py`.
    - The `--dev` flag enables live-reload of the frontend code (and disables HTTP/2 and therefore HTTPS, because HTTP/2 websockets are broken with Hypercorn, and we use a websocket to trigger the reload right now... long story). So if you update frontend code, `build:watch` will rebuild it, then the page will refresh.
