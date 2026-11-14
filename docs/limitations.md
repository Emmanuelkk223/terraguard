# Limitations

TerraGuard is a prototype for exploring satellite-detected burning activity. Read results with these limits in mind.

**What the numbers are**
- A detection is a satellite-observed thermal anomaly, not a confirmed fire or a unique fire event. Other heat sources
  (for example industrial flares) can appear; the FIRMS `type` field is retained and can be used to filter.
- "Active cell-days" count (day, grid cell) pairs with a detection. They depend on the chosen grid size and are not burned area.
- FRP is not a count and is not calibrated between sensors.

**Sensor differences that remain after harmonization**
- A common grid only slightly reduces the VIIRS excess (national mean ratio about 10.8 raw, 9.2 as cell-days) and does not make the
  series measurably more consistent with each other; the ratio varies a lot with activity level, so no single calibration factor exists.
- MODIS and VIIRS flag the same cell on the same day only a small minority of the time (about 2-8% of cell-days in a typical month),
  partly because of different overpass times, viewing geometry and geolocation. The shared share rises with larger cells.
- Confidence classes are product-specific categories, not comparable probabilities.
- The default series excludes NOAA-20/21 to keep overpass opportunity constant. Terra and Aqua overpass times have drifted by about
  65 minutes in opposite directions since 2019 (measured), which can create apparent MODIS trends; this is not corrected for.

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
- A fixed "3.5" threshold falsely flags 2-12% of ordinary months with 5-13 baseline years, so TerraGuard calibrates the threshold to the
  baseline size for a 1% false-flag rate on ordinary months (see methodology). The calibration assumes Gaussian noise on the log scale;
  real data may have heavier tails. On the full series 32 of 2,782 scored region-months are flagged (1.15%), many of them the same
  December 2025 event seen in several regions, so independent findings are fewer than flags. Short baselines (5-7 years) can only
  flag very large changes. Flags remain a screening aid, not a verdict.
- No ground-truth labels exist, so classification metrics are not reported. Isolation Forest is compared with the baseline
  (`model_comparison.py`) on agreement, stability and a synthetic sensitivity test only; it shows no clear advantage and is not used
  to produce the dashboard's flags. The older sensor-level experiment in `ml/` is likewise not used.

**Rainfall context and sensitivity**
- Rainfall is a coarse gridded product (~0.5 x 0.625 degrees) sampled at one point per region; it is context, not a regional measurement,
  and the most recent months can be revised. It is available for Ghana and its named regions only, not for custom areas.
- Correlations between burning and rainfall are descriptive and not evidence of cause. Several lags are shown, so some moderate
  values can arise by chance.
- The sensitivity analysis varies grid size, platform set and quality filters; it does not vary the monthly interval, and there is no
  ground truth by which any scenario could be called correct.

**Place search**
- Search covers West Africa (16 countries) but fire data exist for **Ghana only**. A place elsewhere moves the map and says so; it shows no detections.
- Place names and coordinates come from GeoNames, which is crowd-sourced: some villages are missing, names vary in spelling, and several places can share a
  name (the list shows region and coordinates to tell them apart). Population is mostly unknown, so ranking uses administrative importance.
- Choosing a Ghanaian town analyses a square of 10, 25 or 50 km half-width around it (cells are assigned by centre). Small areas hold few grid cells, so
  swings are larger and flags less stable; the Ghana region is offered as a steadier alternative.

**Not provided**
- No fire prediction, early warning, burned-area mapping or statements about specific fires, communities or damage.
- The unauthenticated API and OpenStreetMap tile usage are suitable for development and demonstration only.
