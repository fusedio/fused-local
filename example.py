import numpy as np
import pystac_client
import fused_local
import pystac
import xarray as xr
import odc.stac
from odc.geo.geobox import GeoBox

fused_local.configure_map(
    title="Sentinel-2 demo",
    center="ski santa fe",
    zoom=10,
)


@fused_local.tile
def s2_scene_june(gbox: GeoBox) -> xr.Dataset:
    item = pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_13SDV_20240601_0_L2A"
    )
    print(f"fetched item {item.id} {gbox}")
    data = odc.stac.load([item], ["red", "green", "blue"], geobox=gbox)
    print(f"loaded data for {item.id} {gbox}")
    # idk why odc.stac doesn't handle nodata / offer an option to mask it
    data = data.where(data != 0, np.nan)
    return data


@fused_local.tile
def s2_scene_march(gbox: GeoBox) -> xr.Dataset:
    item = pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_13SDV_20240301_0_L2A"
    )
    data = odc.stac.load([item], ["red", "green", "blue"], geobox=gbox)
    data = data.where(data != 0, np.nan)
    return data


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
