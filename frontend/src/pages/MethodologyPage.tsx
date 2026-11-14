export default function MethodologyPage() {
  return (
    <section className="prose">
      <h2>Methodology and limitations</h2>

      <h3>What the data are</h3>
      <p>
        NASA FIRMS active-fire detections: MODIS (Terra and Aqua, ~1 km pixels) and VIIRS 375 m (Suomi-NPP). A detection is a
        satellite-observed thermal anomaly. It is not a unique fire, not a measure of area burned, and some thermal anomalies come
        from sources other than vegetation fires (for example industrial heat). FRP (fire radiative power) is not a count.
      </p>

      <h3>Why raw counts cannot be added</h3>
      <p>
        The sensors differ in resolution, sensitivity, overpass times, viewing geometry, detection algorithms and confidence scales.
        In our data VIIRS reports several times more detections than MODIS for the same place and week, largely because its pixels are smaller.
      </p>

      <h3>How TerraGuard harmonizes them (method A-0.1)</h3>
      <ol>
        <li>Keep original FIRMS fields and sensor identity; remove only exact duplicates and invalid records.</li>
        <li>Clip to Ghana (geoBoundaries) and assign each detection to a regular grid cell and a UTC day.</li>
        <li>Count <b>active cell-days</b>: a day-cell pair counts once if either sensor detected activity. Detections seen by both are never double-counted, and no event-linking is claimed.</li>
        <li>Use a constant constellation (Terra, Aqua, Suomi-NPP) across all years so changing satellite numbers do not create trends. NOAA-20/21 are available as an option.</li>
        <li>A month is "complete" only when the downloaded data archive covers all of it for every selected sensor product. A day with no detections is not treated as missing data. Incomplete months are hatched and excluded from baselines and from any comparison.</li>
      </ol>

      <h3>Historical comparison and unusual activity</h3>
      <p>
        Each month is compared with the same calendar month in <i>other</i> years (median and MAD of the other years). A month is flagged when its robust score
        exceeds a threshold calibrated to the baseline size (so ordinary months are falsely flagged about 1% of the time), with at least five other
        complete years. Scores use a log scale. Short baselines can only flag very large changes. Every flag shows the baseline, sample size and reason. Flags describe unusual history;
        TerraGuard does not predict fires or issue alerts.
      </p>

      <h3>Sensitivity, rainfall and exports</h3>
      <p>
        The Sensor harmonization page re-runs the analysis under other reasonable choices (grid size, platform set, quality filters) and shows which
        conclusions move. Rainfall (NASA POWER, a coarse gridded product) is shown beside burning as context only: it is an association, not a cause.
        Reports and CSV files carry their area, sensor view, grid and method version, and every chart can be downloaded as a PNG.
      </p>

      <h3>Limitations</h3>
      <ul>
        <li>The common grid does not make the sensors equivalent: VIIRS still detects far more, and the two sensors flag the same cell on the same day only a small minority of the time.</li>
        <li>A day with no detections is ambiguous: no fire, no overpass, cloud, or missing data.</li>
        <li>FRP and confidence are not calibrated between sensors.</li>
        <li>Region totals near borders are approximate (cells take the region of their centre; boundaries are simplified).</li>
        <li>Terra and Aqua overpass times have drifted by about 65 minutes in opposite directions since 2019 (measured on the Sensor harmonization page), which can create apparent trends in the MODIS series. The default series is anchored on Suomi-NPP, whose overpass time is stable, but the drift is not corrected for.</li>
        <li>Converting to cell-days does not make the two sensors measurably more consistent than raw counts do (see the validation table); its benefit is conceptual, not an observed gain in agreement.</li>
        <li>No ground truth exists, so no accuracy, precision or recall is claimed.</li>
      </ul>

      <h3>Credits</h3>
      <p>
        Fire data: NASA FIRMS (LANCE/EOSDIS). Region boundaries: geoBoundaries (CC BY-SA 2.0). Rainfall: NASA POWER. Map tiles: OpenStreetMap contributors.
      </p>
    </section>
  );
}
