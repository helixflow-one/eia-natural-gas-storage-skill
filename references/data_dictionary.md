# Data dictionary

## Regions and source identifiers

| Canonical region | Display name | Latest JSON `series_id` | Historical API `series` facet |
|---|---|---|---|
| `lower48` | U.S. Lower 48 (Contiguous United States) | `png.nw2_epg0_swo_r48_bcf.w` | `NW2_EPG0_SWO_R48_BCF` |
| `east` | East | `png.nw2_epg0_swo_r31_bcf.w` | `NW2_EPG0_SWO_R31_BCF` |
| `midwest` | Midwest | `png.nw2_epg0_swo_r32_bcf.w` | `NW2_EPG0_SWO_R32_BCF` |
| `mountain` | Mountain | `png.nw2_epg0_swo_r34_bcf.w` | `NW2_EPG0_SWO_R34_BCF` |
| `pacific` | Pacific | `png.nw2_epg0_swo_r35_bcf.w` | `NW2_EPG0_SWO_R35_BCF` |
| `south_central` | South Central | `png.nw2_epg0_swo_r33_bcf.w` | `NW2_EPG0_SWO_R33_BCF` |
| `salt` | South Central Salt | `png.nw2_epg0_sso_r33_bcf.w` | `NW2_EPG0_SSO_R33_BCF` |
| `nonsalt` | South Central Nonsalt | `png.nw2_epg0_sno_r33_bcf.w` | `NW2_EPG0_SNO_R33_BCF` |

The mappings are exact identifiers. Do not select a series using display-name substrings.

## Normalized fields

- `report_date`: storage week-ending date, not the publication date.
- `release_date`: publication calendar date when supplied. Midnight in the source does not establish a release time.
- `retrieved_at_utc`: actual fetch timestamp.
- `stocks_bcf`: working gas inventory in billion cubic feet.
- `net_change_bcf`: EIA's official weekly net change. Positive is injection; negative is withdrawal.
- `implied_flow_bcf`: EIA's separate implied-flow measure. Never substitute it for net change.
- `year_ago_stocks_bcf`: source-published comparable prior-year stock for a current release.
- `five_year_average_bcf`: source-published benchmark for a current release.
- `pct_change_yoy` and `pct_vs_five_year`: source-published percentages for a current release.
- `revision_flags`: source revision and reclassification flags plus original source values.
- `freshness_status`: `current`, `stale`, or `unknown` based on the official schedule evaluation.
- `source_url` and `source_kind`: observation provenance.
- `warnings`: missing values, truncation, duplicate removal, arithmetic discrepancies, or freshness limitations.

Historical API observations contain stock levels only. Null comparison or flow fields are intentional; derive them only with a disclosed method.

## Arithmetic tolerances

Regional values are independently rounded. Validation allows up to 5 Bcf between the five major regional stocks and Lower 48, and up to 2 Bcf between South Central and its salt-plus-nonsalt components. A discrepancy is diagnostic; never silently rewrite official figures.

