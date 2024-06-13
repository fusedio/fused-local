import React, { useEffect, useRef, useState } from "react";
import { Map } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import useSWR from "swr";
import { ScatterplotLayer, BitmapLayer } from "@deck.gl/layers";
import { TileLayer } from '@deck.gl/geo-layers';
import type { TileLayerPickingInfo } from '@deck.gl/geo-layers';
import 'maplibre-gl/dist/maplibre-gl.css';

import { InitialMapState, AppState, TileLayer as TileLayerModel } from './generated/models';
import { MapViewState } from "@deck.gl/core";

const tileUrl = (name: string, vmin: number, vmax: number, hash: string) => `/tiles/${name}/{z}/{x}/{y}.png?vmin=${vmin}&vmax=${vmax}&hash=${hash}`;

function App() {
    const [mapViewState, setMapViewState] = useState<MapViewState>({
        // TODO change default location
        longitude: 0.45,
        latitude: 51.47,
        zoom: 7,
    });
    const prevInitialMapState = useRef<InitialMapState>({ ...mapViewState });
    const [tileLayers, setTileLayers] = useState<TileLayerModel[]>([]);
    const [isLoading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const eventSource = new EventSource("/app_state");

        eventSource.onmessage = (event) => {
          const newState: AppState = JSON.parse(event.data);
          console.log(newState.initial_map_state);

          setTileLayers(newState.layers);

          // Only reposition the map when the initial state defined on the backend
          // has changed from whatever it previously was, i.e. the user adjusted
          // a `configure_map` call.

          // FIXME: somehow an extraneous `padding` property is ending up in the `prevInitialMapState`
        // or the `newState.initial_map_state`. This makes absolutely no sense. Which object it ends up
            // in seems to change depending on whether we copy `mapViewState` into `prevInitialMapState` at
            // the beginning, or copy `newState.initial_map_state` into `prevInitialMapState` at the end.
            // Also, running normally, the `console.log` here will show the `padding` property, but if you
            // breakpoint and step through in the debugger, it doesn't (but it still inserts itself later somehow).
            // So as a stupid hack workaround, we just compare the fields we care about. This is insane.
          if (
            newState.initial_map_state.latitude !==
              prevInitialMapState.current.latitude ||
            newState.initial_map_state.longitude !==
              prevInitialMapState.current.longitude ||
            newState.initial_map_state.zoom !== prevInitialMapState.current.zoom
          ) {
            console.log(
              prevInitialMapState.current,
              newState.initial_map_state
            );
            setMapViewState(newState.initial_map_state);
            prevInitialMapState.current = { ...newState.initial_map_state };
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

            renderSubLayers: props => {
                const { boundingBox } = props.tile;

                return new BitmapLayer(props, {
                    data: null,
                    image: props.data,
                    bounds: [boundingBox[0][0], boundingBox[0][1], boundingBox[1][0], boundingBox[1][1]]
                });
            }
        })
    });

    return <DeckGL
        viewState={mapViewState}
        onViewStateChange={e => setMapViewState(e.viewState)}
        controller
        getTooltip={({ tile }: TileLayerPickingInfo) => tile && `x:${tile.index.x}, y:${tile.index.y}, z:${tile.index.z}`}
        layers={layers}
    >
        {/* <ScatterplotLayer
            data={[
                { position: [-0.05, 51.47], size: 1000 },
                { position: [0.05, 51.47], size: 500 },
                { position: [0.45, 51.47], size: 2000 }
            ]}
            getPosition={d => d.position}
            getRadius={d => d.size}
        /> */}
        <Map
            mapStyle="https://basemaps.cartocdn.com/gl/positron-nolabels-gl-style/style.json"
        />
        <section><aside
            style={{
                position: "absolute",
                top: 0,
                left: 0,
                backgroundColor: "white",
                padding: "0.75rem",
                minWidth: "10rem",
                width: "initial",
                // padding: 10,
                // borderRadius: 5,
                // zIndex: 1,
            }}
        >
            {isLoading && "Loading..."}
            {error && <span style={{ color: 'red' }}>Disconnected from server</span>}
            {tileLayers && <Layers layers={tileLayers} />}
        </aside></section>
    </DeckGL>
}

function Layers({ layers }: { layers: TileLayerModel[] }) {
    return <>
        <h3
            style={{
                margin: "0.3rem 0.1rem"
            }}
        >
            Layers
        </h3>
        {layers.map((layer) => (
            <div key={layer.hash}><samp>{layer.name} - {layer.hash}</samp></div>
        ))}
    </>
}

export default App;
