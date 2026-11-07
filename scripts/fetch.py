"""Snapshot a small GBIF study window into compact, auditable records."""
import argparse
from calendar import monthrange
import concurrent.futures
import gzip
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DATASET = "50c9509d-22c7-4a22-a47d-8c48425ef4a7"
SEARCH = "https://api.gbif.org/v1/occurrence/search"
FILTERS = {
    "datasetKey": DATASET, "country": "GB", "taxonKey": 7707728,
    "decimalLatitude": "50,54", "decimalLongitude": "-6,-2",
    "hasCoordinate": "true", "hasGeospatialIssue": "false",
    "license": "CC0_1_0", "basisOfRecord": "HUMAN_OBSERVATION",
}
PAGE = 300
ROOT = Path(__file__).resolve().parents[1]


def search(year, limit, offset=0, period=None):
    filters = FILTERS | {"year": year, "limit": limit, "offset": offset}
    if isinstance(period, int):
        filters["month"] = period
    elif period:
        filters["eventDate"] = period
    url = SEARCH + "?" + urlencode(filters)
    request = Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": "HerbGap/1.0 (research prototype)"})
    for attempt in range(5):
        try:
            with urlopen(request, timeout=40) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return json.loads(body)
        except (OSError, ValueError):
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def compact(record):
    return [
        record["key"], record.get("speciesKey"), record.get("decimalLatitude"),
        record.get("decimalLongitude"), (record.get("eventDate") or "")[:10],
        record.get("coordinateUncertaintyInMeters"), record.get("license"),
    ]


def snapshot(year, cache, workers):
    def slice_count(period):
        return search(year, 0, period=period)["count"]

    def load(job):
        period, offset = job
        path = cache / f"{year}-{period}-{offset}.json"
        if path.exists():
            return json.loads(path.read_text())
        rows = [compact(row) for row in search(year, PAGE, offset, period)["results"]]
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(rows, separators=(",", ":")))
        temporary.replace(path)
        return rows

    records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        months = list(range(1, 13))
        counts = list(pool.map(slice_count, months))
        slices = []

        def split_dates(month, start, end, total):
            if total < 7000:
                if total:
                    period = f"{year}-{month:02d}-{start:02d},{year}-{month:02d}-{end:02d}"
                    slices.append((period, total))
                return
            if start == end:
                raise ValueError(f"{year}-{month:02d}-{start:02d} has too many records. Split geographically.")
            middle = (start + end) // 2
            spans = [(start, middle), (middle + 1, end)]
            periods = [f"{year}-{month:02d}-{lo:02d},{year}-{month:02d}-{hi:02d}" for lo, hi in spans]
            for (lo, hi), size in zip(spans, pool.map(slice_count, periods)):
                split_dates(month, lo, hi, size)

        for month, total in zip(months, counts):
            if total < 7000:
                slices.append((month, total))
            else:
                split_dates(month, 1, monthrange(year, month)[1], total)
        count = sum(total for _, total in slices)
        if max(total for _, total in slices) >= 10_000:
            raise ValueError("Date slice exceeds 10,000 records. Split further before paging.")
        jobs = [(period, offset) for period, total in slices
                for offset in range(0, total, PAGE)]
        print(f"{year}: {count:,} records across {len(jobs)} pages", flush=True)
        for page_index, page in enumerate(pool.map(load, jobs), 1):
            records.extend(page)
            if page_index % 20 == 0:
                print(f"{year}: {len(records):,}/{count:,}", flush=True)
    unique = {row[0]: row for row in records}
    if len(records) != count or len(unique) != count or search(year, 0)["count"] != count:
        raise RuntimeError(f"GBIF changed while paginating {year}: expected {count}, fetched {len(unique)} unique of {len(records)}. Retry with a fresh cache.")
    path = ROOT / "data" / f"occurrences-{year}.json.gz"
    payload = {
        "year": year, "filters": FILTERS, "source": "https://doi.org/10.15468/ab3s5x",
        "columns": ["gbifID", "speciesKey", "latitude", "longitude", "date", "coordinateUncertaintyM", "license"],
        "records": [unique[key] for key in sorted(unique)],
    }
    path.write_bytes(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), mtime=0))
    print(f"{year}: saved {count:,} records to {path.name}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", type=int, default=[2024, 2025])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--cache", type=Path, default=ROOT / ".gbif-cache")
    options = parser.parse_args()
    options.cache.mkdir(parents=True, exist_ok=True)
    for year in options.years:
        snapshot(year, options.cache, options.workers)
