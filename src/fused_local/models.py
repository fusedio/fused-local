import json
import sys
import pydantic
import subprocess


class TileLayer(pydantic.BaseModel):
    name: str
    hash: str
    max_zoom: int
    min_zoom: int
    vmin: int | float
    vmax: int | float
    visible: bool


class InitialMapState(pydantic.BaseModel):
    title: str | None = None
    longitude: float
    latitude: float
    zoom: int


class AppState(pydantic.BaseModel):
    layers: list[TileLayer]
    initial_map_state: InitialMapState


if __name__ == "__main__":
    # Turn pydantic models into TypeScript.
    # This is used in the build infrastructure:
    # 1. `rye run build_ts` executes this to generate js/generated/models.ts
    # 2. `npm run build` calls `rye run build_ts`
    # 3. `npm run build:watch` watches this file for changes, as well as all the JS, and calls `npm run build`

    schema = AppState.model_json_schema(mode="serialization")
    # print(json.dumps(schema, indent=2))

    args = ["npx", "json2ts"]
    if len(sys.argv) == 2:
        args.extend(["-o", sys.argv[1]])
    subprocess.run(args, text=True, input=json.dumps(schema), check=True)
