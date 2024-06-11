import React from "react";
import { Map } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer } from "@deck.gl/layers";
import 'maplibre-gl/dist/maplibre-gl.css';

function App() {
    return <DeckGL
        initialViewState={{
            longitude: 0.45,
            latitude: 51.47,
            zoom: 7
        }}
        controller
    >
        <ScatterplotLayer
            data={[
                { position: [-0.05, 51.47], size: 1000 },
                { position: [0.05, 51.47], size: 500 },
                { position: [0.45, 51.47], size: 2000 }
            ]}
            getPosition={d => d.position}
            getRadius={d => d.size}
        />
        <Map
            mapStyle="https://basemaps.cartocdn.com/gl/positron-nolabels-gl-style/style.json"
        />
    </DeckGL>
}

export default App;
