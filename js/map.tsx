import { TileLayer } from "@deck.gl/geo-layers";
import { BitmapLayer } from "@deck.gl/layers";
import DeckGL from "@deck.gl/react";
import { produce } from "immer";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useState } from "react";
import { Map } from "react-map-gl/maplibre";

import { MapViewState } from "@deck.gl/core";
import {
    AppState,
    InitialMapState,
    TileLayer as TileLayerModel,
} from "./generated/models";

const tileUrl = (name: string, vmin: number, vmax: number, hash: string) =>
    `/tiles/${name}/{z}/{x}/{y}.png?vmin=${vmin}&vmax=${vmax}&hash=${hash}`;

function App() {
    const [mapViewState, setMapViewState] = useState<MapViewState>({
        // TODO change default location
        longitude: 0.45,
        latitude: 51.47,
        zoom: 7,
    });
    const [tileLayers, setTileLayers] = useState<TileLayerModel[]>([]);
    const [title, setTitle] = useState<string | null>(null);
    const [isLoading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const eventSource = new EventSource("/app_state");

        let prevInitialMapState: InitialMapState = { ...mapViewState };
        eventSource.onmessage = (event) => {
            const newState: AppState = JSON.parse(event.data);

            setTileLayers(newState.layers);
            setTitle(newState.initial_map_state.title || null);

            // Only reposition the map when the initial state defined on the backend
            // has changed from whatever it previously was, i.e. the user adjusted
            // a `configure_map` call.

            // FIXME: somehow an extraneous `padding` property is ending up in the `prevInitialMapState`
            // or the `newState.initial_map_state`. This makes absolutely no sense. Which object it ends up
            // in seems to change depending on whether we copy `mapViewState` into `prevInitialMapState` at
            // the beginning, or copy `newState.initial_map_state` into `prevInitialMapState` at the end.
            // Also, running normally, the `console.log` here will show the `padding` property, but if you
            // breakpoint and step through in the debugger, it doesn't (but it still inserts itself later somehow).
            // Also, useRef doesn't help either.
            // So as a stupid hack workaround, we just compare the fields we care about. This is insane.
            if (
                newState.initial_map_state.latitude !==
                    prevInitialMapState.latitude ||
                newState.initial_map_state.longitude !==
                    prevInitialMapState.longitude ||
                newState.initial_map_state.zoom !== prevInitialMapState.zoom
            ) {
                console.log(prevInitialMapState, newState.initial_map_state);
                setMapViewState(newState.initial_map_state);
                prevInitialMapState = { ...newState.initial_map_state };
            }

            setError(null);
            setLoading(false);
        };

        eventSource.onerror = (event) => {
            console.log("EventSource failed:", event);
            setError("EventSource failed: " + event);
        };

        return () => eventSource.close();
    }, []);

    const layers = tileLayers.map((layer) => {
        return new TileLayer({
            id: layer.name,
            data: tileUrl(layer.name, layer.vmin, layer.vmax, layer.hash),
            minZoom: layer.min_zoom,
            maxZoom: layer.max_zoom,
            pickable: true,
            visible: layer.visible,

            renderSubLayers: (props) => {
                const { boundingBox } = props.tile;

                return new BitmapLayer(props, {
                    data: null,
                    image: props.data,
                    bounds: [
                        boundingBox[0][0],
                        boundingBox[0][1],
                        boundingBox[1][0],
                        boundingBox[1][1],
                    ],
                });
            },
        });
    });

    return (
        <DeckGL
            viewState={mapViewState}
            onViewStateChange={(e) => setMapViewState(e.viewState)}
            controller={{
                keyboard: false,
            }}
            // getTooltip={({ tile }: TileLayerPickingInfo) =>
            //     tile &&
            //     `x:${tile.index.x}, y:${tile.index.y}, z:${tile.index.z}`
            // }
            layers={layers}
        >
            <Map mapStyle="https://basemaps.cartocdn.com/gl/positron-nolabels-gl-style/style.json" />
            <section>
                <aside
                    style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        backgroundColor: "rgba(255, 255, 255, 0.9)",
                        backdropFilter: "blur(5px)",
                        padding: "0.75rem",
                        minWidth: "10rem",
                        width: "initial",
                        // padding: 10,
                        // borderRadius: 5,
                        // zIndex: 1,
                    }}
                >
                    {title && <h2 style={{margin: "0.3rem 0"}}>{title}</h2>}

                    {isLoading && "Loading..."}
                    {error && (
                        <span style={{ color: "red" }}>
                            Disconnected from server
                        </span>
                    )}
                    {tileLayers && (
                        <Layers layers={tileLayers} onChange={setTileLayers} />
                    )}
                </aside>
            </section>
        </DeckGL>
    );
}

function Layers({
    layers,
    onChange,
}: {
    layers: TileLayerModel[];
    onChange: (layers: TileLayerModel[]) => void;
}) {
    const inputStyle: React.CSSProperties = {
        display: "initial",
        maxWidth: "4rem",
        margin: "0 0.2rem",
        padding: "0.2rem 0.4rem",
    };
    const labelStyle: React.CSSProperties = {
        display: "initial",
        margin: "0 0.2rem",
        fontWeight: "initial"
    };
    return (
        <>
            <details style={{margin: 0}} open>
                <summary>
                    <h4
                        style={{
                            margin: "0.3rem 0.1rem",
                            display: "inline",
                        }}
                    >
                        Layers
                    </h4>
                </summary>
                {layers
                    .map((layer, index) => (
                        <div key={layer.hash}>
                            <label style={labelStyle}>
                                <input
                                    type="checkbox"
                                    checked={layer.visible}
                                    onChange={(e) => {
                                        onChange(
                                            produce(layers, (draft) => {
                                                draft[index].visible =
                                                    e.target.checked;
                                            }),
                                        );
                                    }}
                                />
                                <samp>
                                    {layer.name} - {layer.hash.slice(0, 8)}
                                </samp>
                            </label>
                            <label style={labelStyle}>
                                vmin:
                                <input
                                    type="number"
                                    style={inputStyle}
                                    value={layer.vmin}
                                    onChange={(e) => {
                                        onChange(
                                            produce(layers, (draft) => {
                                                draft[index].vmin = Number(
                                                    e.target.value,
                                                );
                                            }),
                                        );
                                    }}
                                />
                            </label>
                            <label style={labelStyle}>
                                vmax:
                                <input
                                    type="number"
                                    style={inputStyle}
                                    value={layer.vmax}
                                    onChange={(e) => {
                                        onChange(
                                            produce(layers, (draft) => {
                                                draft[index].vmax = Number(
                                                    e.target.value,
                                                );
                                            }),
                                        );
                                    }}
                                />
                            </label>
                        </div>
                    ))
                    .reverse()}
            </details>
        </>
    );
}

export default App;
