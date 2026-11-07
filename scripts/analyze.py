"""Build a browser-ready coverage audit and a fixed temporal benchmark."""
from collections import Counter, defaultdict
from datetime import date
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIES = {3120060: ("Yarrow", "Achillea millefolium"), 8208358: ("Ribwort plantain", "Plantago lanceolata")}
CELL_KM = 10
BUDGET = 20
MAX_UNCERTAINTY_M = 1000
REFERENCE_LAT = math.radians(52)
RADIUS_KM = 6371.0088
SCALE = math.cos(REFERENCE_LAT)
BOUNDS = (-6, 50, -2, 54)


def project(lon, lat):
    return RADIUS_KM * math.radians(lon) * SCALE, RADIUS_KM * math.sin(math.radians(lat)) / SCALE


def inverse(x, y):
    return math.degrees(x / (RADIUS_KM * SCALE)), math.degrees(math.asin(y * SCALE / RADIUS_KM))


def grid(lon, lat):
    return tuple(math.floor(km / CELL_KM) for km in project(lon, lat))


def center(cell):
    return inverse(*(CELL_KM * (axis + 0.5) for axis in cell))


def inside_ring(point, ring):
    x, y = point
    inside = False
    a = ring[-1]
    for b in ring:
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
        a = b
    return inside


def land_cells(coast):
    west, south, east, north = BOUNDS
    left, bottom = grid(west, south)
    right, top = grid(east, north)
    for x in range(left, right + 1):
        for y in range(bottom, top + 1):
            cell = x, y
            point = center(cell)
            if west <= point[0] <= east and south <= point[1] <= north and any(
                inside_ring(point, outer) and not any(inside_ring(point, hole) for hole in holes)
                for outer, *holes in coast
            ):
                yield cell


def load_year(year):
    with gzip.open(ROOT / "data" / f"occurrences-{year}.json.gz", "rt") as stream:
        snapshot = json.load(stream)
    cells = defaultdict(list)
    removed = Counter()
    for _, species, lat, lon, timestamp, uncertainty, license_url in snapshot["records"]:
        if not license_url or "/zero/1.0" not in license_url:
            removed["license"] += 1
            continue
        if uncertainty is None or not 0 <= uncertainty <= MAX_UNCERTAINTY_M:
            removed["coordinate_uncertainty"] += 1
            continue
        try:
            event_day = date.fromisoformat(timestamp)
        except ValueError:
            removed["event_date"] += 1
            continue
        if event_day.year != year or lat is None or lon is None:
            removed["year_or_coordinates"] += 1
            continue
        cells[grid(lon, lat)].append((species, event_day.isoformat()))
    return cells, {"input": len(snapshot["records"]), "excluded": dict(removed),
                   "used": sum(map(len, cells.values()))}


def summarize(records, focal):
    target = sum(species == focal for species, _ in records)
    background = len({day for species, day in records if species != focal})
    return target, background


def rank(eligible, targets):
    """Rank from training data only. All methods get the same eligible cells."""
    ranked = []
    for cell, days in eligible.items():
        distances = [CELL_KM * math.dist(cell, other) for other in targets]
        nearest = min(distances)
        nearby = sum(distance <= 30 for distance in distances)
        context = sum(math.exp(-distance / 15) for distance in distances if distance <= 30)
        score = context * days / (days + 5)
        ranked.append({"cell": cell, "days": days, "nearby": nearby, "nearest": nearest, "score": score})
    return {
        "herbgap": sorted(ranked, key=lambda row: (-row["score"], row["cell"])),
        "nearest": sorted(ranked, key=lambda row: (row["nearest"], row["cell"])),
        "activity": sorted(ranked, key=lambda row: (-row["days"], row["cell"])),
    }


def evaluate(ranking, future, focal):
    selected = ranking[:BUDGET]
    hit = sum(any(species == focal for species, _ in future.get(row["cell"], ())) for row in selected)
    covered = sum(bool(future.get(row["cell"])) for row in selected)
    return {"hits": hit, "selected": len(selected), "anyReporting": covered}


def analyze(coast, training, future):
    cells = sorted(set(land_cells(coast)) | training.keys())
    results = {}
    for focal, (name, latin) in SPECIES.items():
        evidence = {cell: summarize(training.get(cell, ()), focal) for cell in cells}
        targets = {cell for cell, (count, _) in evidence.items() if count}
        eligible = {cell: days for cell, (count, days) in evidence.items() if not count and days >= 3}
        ranking = rank(eligible, targets)
        by_cell = {row["cell"]: row for row in ranking["herbgap"]}
        shortlist = [row["cell"] for row in ranking["herbgap"][:BUDGET]]
        results[str(focal)] = {
            "name": name, "latin": latin, "eligible": len(eligible), "focalRecords": sum(count for count, _ in evidence.values()),
            "benchmark": {method: evaluate(rows, future, focal) for method, rows in ranking.items()},
            "cells": [
                [x, y, count, days,
                 by_cell[(x, y)]["nearby"] if (x, y) in by_cell else None,
                 round(by_cell[(x, y)]["nearest"], 1) if (x, y) in by_cell else None,
                 round(by_cell[(x, y)]["score"], 4) if (x, y) in by_cell else None]
                for (x, y), (count, days) in evidence.items()
            ],
            "shortlist": shortlist,
        }
    return results


def main():
    coast = json.loads((ROOT / "data" / "coast.json").read_text())
    training, train_counts = load_year(2024)
    future, test_counts = load_year(2025)
    results = analyze(coast, training, future)
    west, south, east, north = BOUNDS
    output = {
        "coast": [[[[round(v, 2) for v in project(*point)] for point in ring] for ring in polygon] for polygon in coast],
        "view": [*project(west, south), *project(east, north)],
        "cellKm": CELL_KM, "budget": BUDGET, "counts": {"2024": train_counts, "2025": test_counts}, "species": results,
    }
    (ROOT / "data" / "audit.json").write_text(json.dumps(output, separators=(",", ":")) + "\n")
    print(json.dumps({"counts": output["counts"], "results": {
        item["name"]: {key: item[key] for key in ("eligible", "focalRecords", "benchmark")}
        for item in results.values()
    }}, indent=2))


if __name__ == "__main__":
    main()
