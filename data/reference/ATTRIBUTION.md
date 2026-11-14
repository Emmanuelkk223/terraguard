# Reference boundaries

Source: geoBoundaries (gbOpen release), https://www.geoboundaries.org/ ,
fetched via the geoBoundaries API on 2026-11-14 (simplified geometry).

| File | Level | Year represented | Licence |
|---|---|---|---|
| GHA_ADM0.geojson | Country | 2007 | Public Domain |
| GHA_ADM1.geojson | 16 regions | 2021 | CC BY-SA 2.0 (attribution + share-alike) |

Simplified geometries are used for clipping and region assignment; boundaries
are approximate and not legal boundaries. Detections near region borders may
be assigned to a neighbouring region.

## Place names

`west_africa_places.parquet`: populated places, regions and countries of the 16 West African countries, built by
`python -m data_pipeline.gazetteer` from GeoNames (https://www.geonames.org/, licence CC BY 4.0). The downloaded files are kept unchanged in
`data/raw/gazetteer/`. GeoNames records population as unknown for most places, so population is not used to filter or rank; abandoned and
historical places are dropped. Coordinates and names are crowd-sourced and can be wrong or missing; a small village may be absent.
