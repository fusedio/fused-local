import fused_local
import geocube
import geocube.vector
import geopandas as gpd
import odc.stac
import planetary_computer
import pystac_client
from odc.geo.geobox import GeoBox

fused_local.configure_map(
    title="S2 composites",
    center="North Dakota, USA",
    zoom=8,
)

@fused_local.tile
def flare_hotspots(gbox: GeoBox) -> gpd.GeoDataFrame:
    # NOTE: this offers a very natural way to support parameters: just add typed arguments to the function...
    # Also documentation/description via docstring?
    # If a func makes multiple layers, that could show up as a whole group?
    # And it could return something(s), as the "primary" output; other layers are "debug" and can all be toggled on/off?
    # Could even offer an easy "debug: bool" parameter to add some if statements

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
    fused_local.map(avg_max, "SWIR2 average 2-week max", colormap="inferno", visible=False, order=1)
    # TODO: if `map` is given a dask variable, wait to compute it until the tile func has finished, then compute all at once
    # (also depending on visibility)

    rgb = stack['red', 'green', 'blue']
    rgb_median = rgb.median("time")
    fused_local.map(rgb_median, order=0)  # TODO infer title from variable name via AST
    # NOTE: order is relative within the func; keep multiple funcs from stomping on each other

    hotspots = avg_max > 0.6
    fused_local.map(hotspots, "Hotspots raster", colormap="inferno")

    # TODO jesus do you need yet another library to vectorize??
    hotspots_df = geocube.vector.vectorize(hotspots).centroid
    # TODO geoseries vs gdf
    fused_local.map(hotspots_df)

    return hotspots_df  # use identity to recognize when a `map` is called with primary output

@fused_local.file
def us_counties() -> gpd.GeoDataFrame:
    # this is all just a chatgpt hallucination and doesn't work, but demo of what it could look like
    counties = gpd.read_file("https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_110m_admin_1_states_provinces.shp")
    return counties["name", "geometry", "pop_est", "gdp_md_est"]

@fused_local.region
def hotspots_summary(gbox: GeoBox) -> gpd.GeoDataFrame:
    counties = us_counties()
    overlap: gpd.GeoDataFrame = counties[counties.intersects(gbox.geographic_extent)]

    hotspots: gpd.GeoDataFrame = flare_hotspots.tile_over(overlap)
    # TODO how to deal with CRS? if this were an area calculation, we'd want to use an appropriate equal-area projection, etc.
    # TODO how to cache this? `tile_over` will end up converting overlap to an AOI/GeoBox, which I guess will be the cache key?

    # NOTE: also just a sketch, not quite right
    joined = overlap.sjoin(hotspots, how="inner")
    summary = joined.groupby("name").sum("flares")

    # QUESTION: we're using `region` here, but what if we'd used `tile` and then returned
    # a thing that was bigger than the tile? could we intelligently cache that, maybe tile internally,
    # and avoid re-running? would that be a way to avoid `region`?
    # tricky part might be that we'd initally have made a tile layer on the map, which would launch
    # bunch of reqs. once the first finished and we realized what was going on, we'd want to cancel the others
    # and replace the tile layer with a static one.
    # Explicit is probably better than implicit here in the end.

    fused_local.map(summary)

    return summary