import React, { useEffect, useState } from "react";
import { Map } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import useSWR from "swr";
import { ScatterplotLayer, BitmapLayer } from "@deck.gl/layers";
import { TileLayer } from '@deck.gl/geo-layers';
import type { TileLayerPickingInfo } from '@deck.gl/geo-layers';
import 'maplibre-gl/dist/maplibre-gl.css';

const tileUrl = (name: string, vmin: number = 0, vmax: number = 8000) => `http://127.0.0.1:8000/tiles/${name}/{z}/{x}/{y}.png?vmin=${vmin}&vmax=${vmax}`;

function App() {
    const [data, setData] = useState<string[]>([]);
    const [isLoading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string|null>(null);

    useEffect(() => {
        const eventSource = new EventSource("http://127.0.0.1:8000/state");

        eventSource.onmessage = (event) => {
            setLoading(false);
            const state = JSON.parse(event.data);
            console.log(state);
            setData(state);
        };

        eventSource.onerror = (event) => {
            console.log("EventSource failed:", event);
            setError("EventSource failed: " + event);
        };

        return () => eventSource.close();
    }, []);

    const layers = data?.map((name) => {
        return new TileLayer({
            id: name,
            data: tileUrl(name),
            minZoom: 7,
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
            longitude: 0.45,
            latitude: 51.47,
            zoom: 7
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
            {data && <Layers layerNames={data} />}
        </aside></section>
    </DeckGL>
}

interface LayersProps {
    layerNames: string[];
}

function Layers({ layerNames }: LayersProps) {
    return <>
        <h3
            style={{
                margin: "0.3rem 0.1rem"
            }}
        >
            Layers
        </h3>
        {layerNames.map((name) => (
            <div><samp key={name}>{name}</samp></div>
        ))}
    </>
}

export default App;