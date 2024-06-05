from typing import Callable

import attr
import morecantile
import numpy as np
import rio_tiler.errors
import rio_tiler.io
import rio_tiler.models
import rio_tiler.types
import xarray as xr
from odc.geo.geobox import GeoBox

RasterOut = np.ndarray | xr.DataArray
Udf = Callable[[GeoBox], RasterOut]


class FusedReader(rio_tiler.io.BaseReader):
    input: Udf = attr.field()

    def tile(
        self,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        tilesize: int = 256,
    ) -> rio_tiler.models.ImageData:
        if not self.tile_exists(tile_x, tile_y, tile_z):
            raise rio_tiler.errors.TileOutsideBounds(
                f"Tile {tile_z}/{tile_x}/{tile_y} is outside {self.input} bounds"
            )

        tile_bounds = self.tms.xy_bounds(morecantile.Tile(x=tile_x, y=tile_y, z=tile_z))
        dst_crs = self.tms.rasterio_crs

        gbox = GeoBox.from_bbox(tile_bounds, dst_crs, shape=tilesize)
