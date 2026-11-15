"""Search the West Africa gazetteer by town, city, region or country (offline, accent- and case-insensitive).

Ranking, best first: exact name, name starts with the query, a word of the name starts with it, an alternate
name matches, the query appears inside the name, all typed words appear. GeoNames population is mostly unknown,
so ties are broken by administrative importance (capital > regional seat > district seat), then by whether
TerraGuard has fire data for the place, then by name length.

A trailing country ("Kumasi, Ghana", "Kumasi Ghana", "Abidjan Ivory Coast") restricts the search to that country.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .gazetteer import normalise

# Countries for which TerraGuard has processed fire data: Ghana in full detail, the others at country level.
# Add a code here only once its data are processed.
COVERED_COUNTRIES = frozenset({"GH", "CI", "TG", "BF", "BJ", "CV", "GM", "GN", "GW", "LR", "ML", "MR", "NE", "NG", "SN", "SL"})
MIN_QUERY_CHARS = 2
MAX_RESULTS = 20
ALIASES = {  # other common ways to write a country
    "ivory coast": "CI", "cote divoire": "CI", "cote d ivoire": "CI", "gambia": "GM", "cape verde": "CV", "cabo verde": "CV",
    "guinea bissau": "GW", "sierra leone": "SL", "burkina": "BF",
}


class Gazetteer:
    """In-memory place index. Build once, search many times."""

    def __init__(self, table: pd.DataFrame) -> None:
        self.table = table.reset_index(drop=True)
        self.norm = self.table["norm"].fillna("").astype(str)
        alt = self.table["alt_norm"].fillna("").astype(str)
        for alias, code in ALIASES.items():  # 'ivory coast' must find Côte d'Ivoire the country
            is_country = (self.table["kind"] == "country") & (self.table["country_code"] == code)
            alt = alt.where(~is_country, alt + " " + alias)
        self.alt = " " + alt + " "
        self._cache: dict[tuple, list[dict]] = {}
        self.names = (" " + self.norm + " ")
        countries = self.table[self.table["kind"] == "country"]
        self.country_names = {row.norm: row.country_code for row in countries.itertuples()}
        self.country_names.update(ALIASES)
        self.iso2 = {code.lower() for code in countries["country_code"]}
        self.rank = self.table["seat_rank"].fillna(0).to_numpy(float)
        self.population = self.table["population"].fillna(0).to_numpy(float)
        self.length = self.norm.str.len().to_numpy(float)
        self.codes = self.table["country_code"].to_numpy()
        self.kinds = self.table["kind"].to_numpy()

    @classmethod
    def load(cls, path: str | Path) -> "Gazetteer":
        return cls(pd.read_parquet(path))

    def _split_country(self, query: str) -> tuple[str, str | None]:
        """('kumasi ghana') -> ('kumasi', 'GH'); the country must be the trailing words of the query."""
        if "," in query:
            head, _, tail = query.rpartition(",")
            tail_norm = normalise(tail)
            code = self.country_names.get(tail_norm) or (tail_norm.upper() if tail_norm in self.iso2 else None)
            if code and normalise(head):
                return normalise(head), code
            return normalise(query.replace(",", " ")), None
        tokens = normalise(query).split()
        for k in (3, 2, 1):
            if len(tokens) > k and (candidate := " ".join(tokens[-k:])) in self.country_names:
                return " ".join(tokens[:-k]), self.country_names[candidate]
        return " ".join(tokens), None

    def search(self, query: str, limit: int = 8) -> list[dict]:
        text, country = self._split_country(query)
        if len(text) < MIN_QUERY_CHARS:
            return []
        key = (text, country, limit)
        if key not in self._cache:
            if len(self._cache) >= 512:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = self._search(text, country, limit)
        return self._cache[key]

    def _search(self, text: str, country: str | None, limit: int) -> list[dict]:
        pool = np.ones(len(self.table), dtype=bool) if country is None else self.codes == country
        names, alt = self.names[pool], self.alt[pool]
        needle = " " + text
        exact = (names == f" {text} ").to_numpy()
        starts = names.str.startswith(needle, na=False).to_numpy()
        word = names.str.contains(needle, regex=False).to_numpy()
        # The remaining scans are slower; they only matter when strong matches are scarce.
        none = np.zeros(len(names), dtype=bool)
        alt_exact = alt_word = inside = all_tokens = none
        if (exact | starts | word).sum() < MAX_RESULTS * 2:
            alt_exact = alt.str.contains(f" {text} ", regex=False).to_numpy()
            alt_word = alt.str.contains(needle, regex=False).to_numpy()
            inside = names.str.contains(text, regex=False).to_numpy()
            tokens = text.split()
            if len(tokens) > 1:
                both = names + alt
                all_tokens = np.ones(len(names), dtype=bool)
                for token in tokens:
                    all_tokens &= both.str.contains(token, regex=False).to_numpy()

        score = np.select(
            [exact, starts, alt_exact, word, alt_word, inside, all_tokens], [1000, 800, 700, 600, 450, 300, 250], default=0
        ).astype(float)
        hit = score > 0
        if not hit.any():
            return []
        index = np.flatnonzero(pool)[hit]
        score = score[hit]
        kinds = self.kinds[index]
        score += np.where((kinds == "country") & (score >= 1000), 300, 0)  # typing a country's exact name finds the country first
        score += np.where((kinds == "region") & (score >= 800), 150, 0)
        score += self.rank[index] * 40
        score += np.where(np.isin(self.codes[index], list(COVERED_COUNTRIES)), 60, 0)
        score += np.where(self.codes[index] == "GH", 45, 0)  # Ghana first: on an otherwise equal match, a Ghanaian place wins
        score += np.minimum(25, np.log10(self.population[index] + 1) * 5)
        score -= np.minimum(60, self.length[index] * 0.5)  # prefer the shorter, more specific name on a tie
        order = np.argsort(-score, kind="stable")[: max(1, min(limit, MAX_RESULTS))]
        return [self._record(int(i)) for i in index[order]]

    def _record(self, i: int) -> dict:
        row = self.table.iloc[i]
        region = row.get("ghana_region")
        region = None if pd.isna(region) else str(region)
        admin = region or (str(row["admin1"]) if isinstance(row["admin1"], str) and row["admin1"] else None)
        record = {
            "id": int(row["id"]), "name": str(row["name"]), "kind": str(row["kind"]),
            "admin1": admin, "country": str(row["country"]), "country_code": str(row["country_code"]),
            "lat": float(row["lat"]), "lon": float(row["lon"]),
            "covered": str(row["country_code"]) in COVERED_COUNTRIES,
            "region": region,
        }
        box = [row.get("west"), row.get("south"), row.get("east"), row.get("north")]
        if all(isinstance(v, (int, float)) and not math.isnan(v) for v in box):
            record["bbox"] = [float(v) for v in box]
        return record
