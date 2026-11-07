# HerbGap

HerbGap is a medicinal-plant field atlas for volunteer recording coordinators. It shows yarrow and ribwort plantain sightings alongside background recording activity, explains why a grid cell appears on a survey shortlist, and exports the shortlist as CSV.

**EthnoHack 2026 · Track 3 · Biodiversity & Sustainability**

## Run locally

Requires Python 3.10 or newer. From this directory:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
```

Open http://127.0.0.1:8766. The atlas uses the included snapshot and has no API calls or runtime package dependencies. Select a species, compare the two map layers, and click a cell or shortlist row for evidence. Use arrow keys to move between adjacent map cells and the CSV button to export the shortlist.

## Reproduce the analysis

```sh
python3 scripts/analyze.py
```

The script reads the two included compact GBIF snapshots and regenerates `data/audit.json`. To retrieve a new snapshot, run `python3 scripts/fetch.py --cache .gbif-cache` before running the analysis. Refreshes can differ as GBIF ingests or corrects records. The script partitions date queries to limit deep pagination and verifies counts and unique IDs. If GBIF changes during collection, retry with an empty cache.

## Method

1. Use CC0 iNaturalist human observations of vascular plants via GBIF from the study window at 50–54° N and 6–2° W, with the GB country code and no flagged geospatial issue. Exclude records without a usable event date or recorded coordinate uncertainty of at most 1 km.
2. Assign points to 10 km squares in a spherical Lambert cylindrical equal-area projection with a 52° standard parallel. Display cells with land centers or valid 2024 reports.
3. Count focal reports and distinct days with other vascular plant reports in each cell. Candidates have zero focal reports and at least three background reporting days in 2024.
4. Score each candidate by summing exponentially distance-weighted occupied target cells within 30 km, then multiply by `days / (days + 5)`. The baseline scores use nearest target cell distance or background days alone. All three methods use the same candidate pool, 20-cell budget and deterministic coordinate tie-break.
5. Check whether each selected cell received a qualifying target report in 2025. Also report how many selected cells had any qualifying plant records that year. The evaluation uses 2025 only for outcomes.

Unique dates reduce the influence of multiple uploads on the same day. They do not measure actual hours in the field. Future reports reflect observer choices and cannot establish species absence, actual visit yield, abundance, change, or safe harvesting. The evaluation is a single region and temporal split with no prospective survey.

## 2025 benchmark

| Ranking | Yarrow | Ribwort plantain |
| --- | ---: | ---: |
| HerbGap | 11 / 20 | 10 / 20 |
| Nearest target cell | 5 / 20 | 4 / 20 |
| Highest background activity | 10 / 20 | 7 / 20 |

All selected cells received some qualifying plant reporting in 2025. HerbGap gained one yarrow cell and three ribwort plantain cells over the strongest baseline in this split. The input snapshots contained 36,067 records for 2024 and 43,928 for 2025. After the coordinate-uncertainty filter, 27,951 and 36,359 remained, respectively.

## Sources and attribution

- iNaturalist contributors, iNaturalist (2026). [iNaturalist Research-grade Observations](https://doi.org/10.15468/ab3s5x), accessed via GBIF on November 7, 2026. Occurrence-level CC0 filter. The snapshot retains GBIF record IDs and uses no media or observer names.
- [Natural Earth 1:50m country boundaries](https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson), v5.1.2, public domain. The included polygons are the UK subset around the study window.
- European Medicines Agency monographs for [yarrow](https://www.ema.europa.eu/en/medicines/herbal/millefolii-herba) and [ribwort plantain](https://www.ema.europa.eu/en/medicines/herbal/plantaginis-lanceolatae-folium) informed species selection.
- [BSBI Atlas 2020 recorder guidance](https://bsbi.org/wp-content/uploads/dlm_uploads/Atlas_2020_Guidance_for_VCRs_v4.pdf) informed the survey prioritization workflow.

The application, analysis scripts, and presentation materials were built for the event with substantial assistance from OpenAI Codex. The ranking and benchmark run deterministically without a language model.
