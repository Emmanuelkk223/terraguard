import { RADII_KM } from "../services/places";
import type { Place } from "../types";

interface Props {
  place: Place;
  radiusKm: number;
  onRadius: (km: number) => void;
  onWholeRegion: () => void;
  onClear: () => void;
}

/** Explains the area chosen through search, and what to do when TerraGuard has no data for the place. */
export default function PlaceBanner({ place, radiusKm, onRadius, onWholeRegion, onClear }: Props) {
  // "Lagos, Lagos, Nigeria" and "Nigeria, Nigeria" read badly: show each distinct name once.
  const where = [place.admin1, place.country].filter((x, i, all): x is string => !!x && x !== place.name && all.indexOf(x) === i).join(", ");
  if (!place.covered) {
    return (
      <div className="place-banner warn" role="status">
        <div>
          <b>{place.name}</b>{where ? `, ${where}` : ""}: <b>no fire data here yet.</b>{" "}
          TerraGuard has processed Ghana only, so the map has moved to {place.name} for orientation and shows no detections there.
        </div>
        <button type="button" className="tool" onClick={onClear}>Back to Ghana</button>
      </div>
    );
  }
  return (
    <div className="place-banner" role="status">
      <div>
        Showing activity within <b>{radiusKm} km</b> of <b>{place.name}</b>
        {where ? ` (${where})` : ""}. {radiusKm <= 10 && "A small area has few grid cells; try the 1 km grid in the header. "}
        Small areas show larger swings, so read flags with care.
      </div>
      <div className="banner-actions">
        <div className="seg" role="group" aria-label="Area size around the place">
          {RADII_KM.map((km) => (
            <button key={km} type="button" className={km === radiusKm ? "on" : ""} onClick={() => onRadius(km)}>{km} km</button>
          ))}
        </div>
        {place.region && <button type="button" className="tool" onClick={onWholeRegion}>Whole {place.region} region</button>}
        <button type="button" className="tool" onClick={onClear}>Clear</button>
      </div>
    </div>
  );
}
