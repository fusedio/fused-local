from functools import singledispatch
import numpy as np
import xarray as xr
import matplotlib.colors

# TODO vendor all this
from stackstac.show import arr_to_png, Range


@singledispatch
def to_png(
    obj,
    range: Range,
    cmap: matplotlib.colors.Colormap | None = None,
    checkerboard: bool = True,
) -> bytes:
    raise TypeError(f"Can't convert {type(obj)} to PNG")


@to_png.register
def ds_to_png(
    ds: xr.Dataset,
    range: Range,
    cmap: str | None = None,
    checkerboard: bool = True,
) -> bytes:
    return to_png(ds.to_dataarray("band"), range, cmap=cmap, checkerboard=checkerboard)


@to_png.register
def da_to_png(
    arr: xr.DataArray,
    range: Range,
    cmap: str | None = None,
    checkerboard: bool = True,
) -> bytes:
    arr = arr.squeeze()
    if arr.ndim == 2:
        assert set(arr.dims) == {"x", "y"}
        arr = arr.expand_dims("band")
    elif arr.ndim == 3:
        assert set(arr.dims) == {"band", "x", "y"}
        nbands = arr.sizes["band"]
        assert 1 <= nbands <= 3, f"Array must have 1-3 bands, not {nbands}."
    else:
        raise ValueError(
            f"Array must only have the dimensions 'x', 'y', and optionally 'band', not {arr.dims!r}"
        )

    arr = arr.transpose("band", "y", "x")

    np_arr = arr.data
    assert isinstance(
        np_arr, np.ndarray
    ), f"Can only handle NumPy-backed xarray for now, not {type(np_arr)}"

    return to_png(np_arr, range, cmap=cmap, checkerboard=checkerboard)


@to_png.register
def np_to_png(
    arr: np.ndarray,
    range: Range,
    cmap: str | None = None,
    checkerboard: bool = True,
) -> bytes:
    """
    Convert numpy array of shape (b, y, x) to 8-bit PNG, where NaN is nodata.

    Can be int, float, or bool, and have 1-3 bands.
    """
    if arr.ndim == 2:
        arr = arr[np.newaxis]

    cm = None
    if arr.shape[0] == 1:
        # Note that if `cmap` is None, this will use the default colormap (usually viridis)
        cm = matplotlib.colormaps.get_cmap(cmap)  # type: ignore
    elif cmap is not None:
        raise ValueError(
            f"Colormaps are only possible on single-band data; this array has {arr.shape[0]} bands."
        )

    return arr_to_png(arr, range, cmap=cm, checkerboard=checkerboard)
