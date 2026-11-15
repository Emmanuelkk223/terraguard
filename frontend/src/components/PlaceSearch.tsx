import { useCallback, useEffect, useId, useRef, useState } from "react";
import { api } from "../services/api";
import { coordinates, kindLabel, subtitle } from "../services/places";
import type { Place } from "../types";

interface Props {
  onSelect: (place: Place) => void;
}

const DEBOUNCE_MS = 180;
const COORDINATES = /^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*$/;

/** "7.95, -1.02" (latitude, longitude in degrees) as a place; null when the text is not a coordinate pair. */
export function parseCoordinates(text: string): Place | null {
  const m = COORDINATES.exec(text);
  if (!m) return null;
  const lat = Number(m[1]), lon = Number(m[2]);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  const inside = lat >= 4 && lat <= 27.7 && lon >= -25.7 && lon <= 16.3; // the West Africa download area
  return {
    id: -1, name: `${lat.toFixed(3)}, ${lon.toFixed(3)}`, kind: "place", admin1: null, country: "Latitude and longitude",
    country_code: "", lat, lon, covered: inside, region: null,
  };
}

/** Type-ahead search for a town, city, region or country across West Africa. */
export default function PlaceSearch({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const [resultsFor, setResultsFor] = useState(""); // the text the current results were fetched for
  const enterWhenReady = useRef(false); // Enter pressed before the results for the current text arrived
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listId = useId();
  const box = useRef<HTMLDivElement>(null);
  const trimmed = query.trim();
  const typedCoordinates = parseCoordinates(trimmed);

  useEffect(() => {
    if (trimmed.length < 2 || typedCoordinates) {
      setResults([]);
      setError(null);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      api
        .searchPlaces(trimmed, 8, controller.signal)
        .then((r) => {
          setResults(r.data);
          setResultsFor(trimmed);
          setActive(0);
          setError(null);
        })
        .catch((e: Error) => !controller.signal.aborted && setError(e.message))
        .finally(() => !controller.signal.aborted && setLoading(false));
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [trimmed]);

  useEffect(() => {
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const choose = useCallback((place: Place) => {
    enterWhenReady.current = false;
    onSelect(place);
    setQuery("");
    setResults([]);
    setResultsFor("");
    setOpen(false);
  }, [onSelect]);

  const fresh = typedCoordinates ? true : resultsFor === trimmed; // results shown belong to what is typed now
  const items: Place[] = typedCoordinates ? [typedCoordinates] : results;

  // Enter pressed while the new results were still loading: pick the best match as soon as they arrive.
  useEffect(() => {
    if (enterWhenReady.current && fresh && items[0]) choose(items[0]);
  }, [fresh, results, choose]); // eslint-disable-line react-hooks/exhaustive-deps

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && trimmed.length >= 2) {
      e.preventDefault();
      if (fresh && items[active]) choose(items[active]);
      else enterWhenReady.current = true; // never pick a suggestion that belongs to an earlier query
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const showList = open && trimmed.length >= 2;
  return (
    <div className="search" ref={box}>
      <label className="search-label" htmlFor={`${listId}-input`}>Find a place</label>
      <input
        id={`${listId}-input`}
        type="search"
        className="search-input"
        placeholder="Town, city, country, or latitude, longitude"
        autoComplete="off"
        value={query}
        role="combobox"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && items[active] ? `${listId}-${active}` : undefined}
        onChange={(e) => { enterWhenReady.current = false; setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      {showList && (
        <ul id={listId} className={`search-list ${fresh ? "" : "stale"}`} role="listbox" aria-label="Matching places" aria-busy={!fresh}>
          {items.map((p, i) => (
            <li
              key={p.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={`search-item ${i === active ? "on" : ""}`}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => { e.preventDefault(); choose(p); }}
            >
              <span className="search-main">
                <b>{p.name}</b>
                <span className="kind">{kindLabel(p)}</span>
              </span>
              <span className="search-sub">
                {subtitle(p)}{p.kind !== "country" && p.kind !== "region" ? ` · ${coordinates(p)}` : ""}
                <span className={`cover ${p.covered ? "yes" : "no"}`}>{p.covered ? "Fire data" : "No data yet"}</span>
              </span>
            </li>
          ))}
          {!items.length && fresh && !loading && !error && (
            <li className="search-empty">No places match “{trimmed}”. Try the nearest larger town, or a region or country name.</li>
          )}
          {error && <li className="search-empty">Search is unavailable right now ({error}).</li>}
          {loading && !items.length && <li className="search-empty">Searching…</li>}
          <li className="search-foot">Searches West Africa. Ghana has the full detail; the other fifteen countries are covered at country level. You can also type latitude, longitude (for example 6.69, -1.62).</li>
        </ul>
      )}
    </div>
  );
}
