from functools import singledispatchmethod
from typing import Callable, Concatenate, Generic, ParamSpec, Self, TypeVar
from weakref import WeakValueDictionary

import geopandas
import xarray
from odc.geo.geobox import GeoBox

VectorMappable = geopandas.GeoDataFrame | geopandas.GeoSeries
RasterMappable = xarray.DataArray | xarray.Dataset
MappableTypes = VectorMappable | RasterMappable

P = ParamSpec("P")
TileR = TypeVar("TileR", bound=MappableTypes)
# TODO is returning non-mappable types ok? Is it just that we only `map` mappable types, but can return whatever?


class TileFunc(Generic[P, TileR]):
    "A wrapped function that runs on a per-tile basis."

    _instances: WeakValueDictionary[str, Self] = WeakValueDictionary()

    func: Callable[Concatenate[GeoBox, P], TileR]
    name: str

    def __init__(self, func: Callable[Concatenate[GeoBox, P], TileR]) -> None:
        self.func = func
        self.name = func.__name__
        if (prev := self._instances.setdefault(self.name, self)) is not self:
            # actually this may be fine
            raise ValueError(f"{self.name} already exists! {prev=}, {self=}")
        super().__init__()

    def __call__(self, gbox: GeoBox, *args: P.args, **kwargs: P.kwargs) -> TileR:
        # TODO caching
        return self.func(gbox, *args, **kwargs)

    def __repr__(self) -> str:
        return f"TileFunc({self.func!r})"

    @singledispatchmethod
    def tile_over(self, aoi, *args: P.args, **kwargs: P.kwargs) -> TileR:
        """
        Run the tile function over a region, automatically splitting it into tiles.

        Internally, the region split into tiles, the tile function runs over each one in
        parallel, and the results are combined back into a single raster or vector
        (matching the output type of the tile function).

        The region can be specified in a few ways:

        * A `GeoDataFrame` or `GeoSeries`
        * An `xarray.DataArray` or `xarray.Dataset` (georeferenced, with spatial
          dimensions and a ``crs`` coordinate)
        * An explicit `GeoBox` (a bounding box with a CRS)

        Results are automatically cached, and any cached input tiles are re-used. (Input
        tiles are also cached as they're generated, as usual.)
        """
        ...
        # TODO support controlling tiling parameters (CRS, size, etc.)

        # TODO when run over a vector, only run over tiles actually overlapping the geometries,
        # not over the whole bbox. Same for a raster (if it's not dask): don't run over NaN regions?
        # QUESTION: this is more like a spatial join then. Should we just encode that explicitly?
        # If we don't, what does the return look like? Is there a column or something that identities
        # which geometry each tile corresponds to?

        # TODO allow chaining some post-process onto each tile for convenience?
        # so say you have tile func that returns rasters, you could vectorize and stuff
        # without having to write a separate tile func. could help with memory.

        # TODO probably shouldn't/can't do this with raster data, could be too huge.
        # even vector can get too huge too? (like building footprints or something).
        # return type could be dask?? (so much nested parallelism :head-exploding:)

        # alternatively, could have convenience functions for common things you actually need to do,
        # like zonal stats, vectorize, etc?

        # QUESTION: how would you describe something like "run this tile function over these 165 cities"?

    @tile_over.register
    def _tile_over_gdf(
        self, aoi: geopandas.GeoDataFrame, *args: P.args, **kwargs: P.kwargs
    ) -> TileR: ...
    @tile_over.register
    def _tile_over_gs(
        self, aoi: geopandas.GeoSeries, *args: P.args, **kwargs: P.kwargs
    ) -> TileR: ...
    @tile_over.register
    def _tile_over_da(
        self, aoi: xarray.DataArray, *args: P.args, **kwargs: P.kwargs
    ) -> TileR: ...
    @tile_over.register
    def _tile_over_ds(
        self, aoi: xarray.Dataset, *args: P.args, **kwargs: P.kwargs
    ) -> TileR: ...
    @tile_over.register
    def _tile_over_gbox(
        self, aoi: GeoBox, *args: P.args, **kwargs: P.kwargs
    ) -> TileR: ...

    # TODO support GeoBoxTiles or GridSpec or whatever


def tile(
    func: Callable[Concatenate[GeoBox, P], TileR],
) -> TileFunc[P, TileR]:
    """
    Decorator for a function that runs on a per-tile basis.

    The function takes a `GeoBox` as its first argument, for the tile it's producing.
    The function will run many times in parallel (in separate Python processes and/or
    threads).

    On the interactive map, it will be called once parallel for every tile in view, and
    will be called more times as the map pans and zooms.

    Therefore, it should have no side effects, and not rely on global variables. It
    should use `cache` for any data that's expensive to compute, or could be shared
    between tiles (though it's often better to use a separate `file` or `region`
    function for that).

    The function _must_ return data that covers only the tile's region. If the function
    would produce data that covers a larger or smaller area, use `region` instead.

    Results are automatically cached.
    """
    return TileFunc(func)


def region(
    func: Callable[Concatenate[GeoBox, P], TileR],
) -> Callable[Concatenate[GeoBox, P], TileR]:
    """
    Decorator for a function to run over a larger region.

    There are some key differences between `region` and `tile`:

        * `region` is only called once for the whole map view, not once per tile in
          view.
        * `region` can return data that covers a larger area than the `GeoBox` it's
          given.
        * `region` is expected to be slower and more resource-intensive than `tile`. So
          by default, it doesn't run automatically when moving the map: you have to
          explicitly click 'run', and will see a spinner/progress bar.

    `region` is commonly used for:

    * Aggregating over a larger area (especially aggregating a tile function using
      `tile_over`). For example:

        * You have a `tile` function that detects trees. You want to count the number of
          trees in a large area.

    * Loading data that's coarsely spatially partitioned. For example:

        * You have a dataset with a separate file per Candian province. Whatever
          province is currently in view, a `region` function will load the file, and
          display the entire province's data on the map. As you pan around within the
          province, the data is already there; nothing new is loaded.

    The function takes a `GeoBox` as its first argument, for the region it's running
    over.

    On the interactive map, it will only be called once for a particular map view when
    you click "run", and it's passed (approximately) the entire region in view as its
    `GeoBox`.

    Results are automatically cached, based on both the input and output area. So if
    you call a `region` function with a small input area (say a city), and it returns
    data for the entire state, subsequent calls for different areas within that state
    will re-use the output data without re-running the function.
    """
    ...

    # TODO return a RegionFunc object, probably has methods like:
    # * `map` - run over a sequence of regions (name tbd)

    # maybe there's some `fused.progress_update` so you can give some feedback?
    # how to have a UI showing which tiles will run when you do `tile_over`?
    # maybe we detect that being called within a `region` function and tell the UI?

    # what about multiple `tile_over`s? How do you do them in parallel?? async??


def file(
    func: Callable[P, TileR],
) -> Callable[P, TileR]:
    """
    Decorator for a function that produces a single piece of spatial data.

    Unlike `tile` and `region`, the function doesn't take a spatial region as a parameter.
    Instead, it can load and return data with any spatial extent.

    Therefore, it's primarily meant for loading data that isn't spatially partitioned.
    For example:

    * Loading a shapefile of U.S. counties
    * Reading a CSV of weather station data
    * Reading a NumPy array of coefficients for a machine learning model

    Results are automatically cached.
    """
    ...


def map(
    obj: MappableTypes,
    title: str,
    *,
    colormap: str | None = None,
    visible: bool = True,
    order: int | None = None,
    range: tuple[float, float] | None = None,
):
    """
    Display raster or vector data on the interactive map.

    `map` must be called within a `tile`, `region`, or `file` function.

    Within a `tile` function, `map` renders a single tile on the map. You can think
    `map` as sending that particular tile to the map to display. (You don't need to
    specify which tile it is, Fused keeps track of which `GeoBox` your tile function was
    called with.)

    This also means that, within one `tile` function, you can show multiple layers on
    the map. This is especially useful when computing multiple things from the same
    data. For example, a raster layer of input imagery, a layer of building-detection
    probabilities, and a vectorized version of the detections.

    note::

        Fused uses the ``title`` to determine which layer the tile goes to, or to add a
        new layer if necessary. Therefore, **the ``title`` should be a constant
        string**. If the ``title`` changes between tiles, you'll end up with lots of
        separate layers!

    Within a `region` function, `map` renders the entire region's data. Fused handles
    displaying the data on the map efficiently when it's large---this may mean tiling it
    internally, or simply transferring it via efficient serialization (GeoArrow).

    Similar to `region`, within a `file` function, `map` renders the entire dataset and
    handles displaying it efficiently. In a `file` function, though, the data must be
    georeferenced, otherwise Fused has no way to know where to place it on the map!

    Layer groups
    ------------

    Each `tile`, `region`, or `file` function acts as a "layer group". Each time you
    call `map` within the function, that defines a layer within the group. In the UI,
    you can toggle an entire layer group (aka function) on and off, or its individual layers.

    Additionally, the object(s) the function returns are the "primary layer". So you might
    have a function that creates a few layers, which are useful to visualize while developing,
    but only one is the real output. In the UI, you can easily disable these "secondary" debugging
    layers. Additionally, your function can take a `debug: bool` parameter. If the secondary layers
    are disabled, Fused will pass `debug=False`, so you can use this in conditionals to avoid unnecessary
    computation that would only be done to show the secondary layers.
    """
    ...
