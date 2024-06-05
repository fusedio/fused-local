import geocube.vector
import pystac_client
import fused_local
import planetary_computer
from odc.geo.geobox import GeoBox
import odc.stac
import geocube

fused_local.configure_map(
    title="S2 composites",
    center="North Dakota, USA",
    zoom=8,
)

gbox: GeoBox = fused_local.current_geobox

# TODO: make getting wgs84 bbox from geobox easier
# TODO: allow searching pystac with geobox?
# TODO: general STAC->raster 1 function, combine search & stack / rasterpandas

catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)

search = catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=tuple(gbox.geographic_extent.boundingbox),
    datetime="2020-06-01/2020-08-01",
    query={"eo:cloud_cover": {"lt": 20}},
    # max_items=20,
    sortby="datetime",
)

items = search.item_collection()
print(f"{len(items)=}")  # TODO allow printing via non-assign statement like streamlit

stack = odc.stac.load(items, groupby="solar_day", geobox=gbox, bands=["swir2", "red", "green", "blue"])

swir2 = stack["swir2"]
twoweek_max = swir2.resample(time="2W").max("time")
avg_max = twoweek_max.mean("time")
fused_local.show(avg_max, "SWIR2 average 2-week max", colormap="inferno", visible=False, order=1)

rgb = stack['red', 'green', 'blue']
rgb_median = rgb.median("time")
fused_local.show(rgb_median, order=0)  # TODO infer title from variable name via AST

hotspots = avg_max > 0.6
fused_local.show(hotspots, "Hotspots raster", colormap="inferno")

# TODO jesus do you need yet another library to vectorize??
hotspots_df = geocube.vector.vectorize(hotspots)
fused_local.show(hotspots_df)
