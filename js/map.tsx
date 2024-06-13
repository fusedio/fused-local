import React, { useEffect, useState } from "react";
import { Map } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import useSWR from "swr";
import { ScatterplotLayer, BitmapLayer } from "@deck.gl/layers";
import { TileLayer } from '@deck.gl/geo-layers';
import type { TileLayerPickingInfo } from '@deck.gl/geo-layers';
import 'maplibre-gl/dist/maplibre-gl.css';

import { MapState, TileLayer as TileLayerModel } from './generated/models';

const tileUrl = (name: string, vmin: number, vmax: number, hash: string) => `http://localhost:8000/tiles/${name}/{z}/{x}/{y}.png?vmin=${vmin}&vmax=${vmax}&hash=${hash}`;

function App() {
    const [mapState, setMapState] = useState<MapState>(
        {
            layers: [],
            // TODO change default location
            longitude: 0.45,
            latitude: 51.47,
            zoom: 7,
        }
    );
    const [isLoading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const eventSource = new EventSource("/map_state");

        eventSource.onmessage = (event) => {
            setLoading(false);
            const state = JSON.parse(event.data);
            console.log(state);
            setMapState(state);
        };

        eventSource.onerror = (event) => {
            console.log("EventSource failed:", event);
            setError("EventSource failed: " + event);
        };

        return () => eventSource.close();
    }, []);

    const layers = mapState.layers.map((layer) => {
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
        initialViewState={{
            longitude: mapState.longitude,
            latitude: mapState.latitude,
            zoom: mapState.zoom
        }}
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
            {error && "Error: " + error}
            {mapState && <Layers layers={mapState.layers} />}
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
