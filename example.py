import numpy as np
import fused_local
import pystac
import xarray as xr
import odc.stac
from odc.geo.geobox import GeoBox

print("foo")

@fused_local.tile
def s2_scene_june(gbox: GeoBox) -> xr.Dataset:
    item = pystac.Item.from_file(
        "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_13SDV_20240601_0_L2A"
    )
    data = odc.stac.load([item], ["red", "green", "blue"], geobox=gbox)
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
