# Limitations

TerraGuard is a prototype for exploring satellite-detected burning activity. Read results with these limits in mind.

**What the numbers are**
- A detection is a satellite-observed thermal anomaly, not a confirmed fire or a unique fire event. Other heat sources
  (for example industrial flares) can appear; the FIRMS `type` field is retained and can be used to filter.
- "Active cell-days" count (day, grid cell) pairs with a detection. They depend on the chosen grid size and are not burned area.
- FRP is not a count and is not calibrated between sensors.

**Sensor differences that remain after harmonization**
- A common grid reduces, but does not remove, the VIIRS excess. VIIRS also detects activity MODIS does not.
- MODIS and VIIRS flag the same cell on the same day only a minority of the time, partly because of different overpass times,
  viewing geometry and geolocation. The shared share rises with larger cells.
- Confidence classes are product-specific categories, not comparable probabilities.
- The default series excludes NOAA-20/21 to keep overpass opportunity constant; Terra's orbital drift in recent years is not modelled.

**Data and coverage**
- Only standard-processing archive data are used for history. Near-real-time data are not mixed in.
- A day with no detections is ambiguous (no fire, no overpass, cloud, or missing data). Months are marked complete based on
  archive coverage of each product, not on observation opportunity.
- Cloud, smoke and view-angle effects on detectability are not modelled.

**Geography**
- Boundaries are simplified geoBoundaries geometries, not legal boundaries. Region totals near borders are approximate because
  each cell takes the region of its centre.
- The download uses a rectangle around Ghana; detections outside the country are excluded before analysis.

**Statistics**
- Baselines use few observations per region-month (at most one per year). The robust score is a screening aid; at region level,
  small counts make flags less stable. Flags are labelled with their baseline size and reliability.
- No ground-truth labels exist, so classification metrics are not reported, and the Isolation Forest experiment in `ml/` is not
  used by the dashboard.

**Not provided**
- No fire prediction, early warning, burned-area mapping or statements about specific fires, communities or damage.
- The unauthenticated API and OpenStreetMap tile usage are suitable for development and demonstration only.
