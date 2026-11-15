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


## West Africa national outlines (WA_ADM0.geojson)

Source: geoBoundaries gbOpen ADM0, simplified geometry, fetched with `python -m data_pipeline.countries` on 2026-11-14. Licences by country:
Ghana, Côte d'Ivoire, Benin: public domain. Togo, Cabo Verde, Guinea-Bissau: Open Data Commons Open Database License 1.0.
Burkina Faso, Gambia, Mali, Nigeria, Sierra Leone: Creative Commons Attribution 4.0. Liberia, Mauritania, Senegal: CC BY 3.0 IGO.
Guinea, Niger: CC BY-SA 2.0. Attribution: geoBoundaries (https://www.geoboundaries.org/), William & Mary geoLab.
