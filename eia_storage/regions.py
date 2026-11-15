"""Canonical region and source-series mappings."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import InputError


@dataclass(frozen=True)
class Region:
    canonical: str
    display_name: str
    latest_series_id: str
    history_series_id: str


REGIONS: dict[str, Region] = {
    "lower48": Region("lower48", "U.S. Lower 48 (Contiguous United States)", "png.nw2_epg0_swo_r48_bcf.w", "NW2_EPG0_SWO_R48_BCF"),
    "east": Region("east", "East", "png.nw2_epg0_swo_r31_bcf.w", "NW2_EPG0_SWO_R31_BCF"),
    "midwest": Region("midwest", "Midwest", "png.nw2_epg0_swo_r32_bcf.w", "NW2_EPG0_SWO_R32_BCF"),
    "mountain": Region("mountain", "Mountain", "png.nw2_epg0_swo_r34_bcf.w", "NW2_EPG0_SWO_R34_BCF"),
    "pacific": Region("pacific", "Pacific", "png.nw2_epg0_swo_r35_bcf.w", "NW2_EPG0_SWO_R35_BCF"),
    "south_central": Region("south_central", "South Central", "png.nw2_epg0_swo_r33_bcf.w", "NW2_EPG0_SWO_R33_BCF"),
    "salt": Region("salt", "South Central Salt", "png.nw2_epg0_sso_r33_bcf.w", "NW2_EPG0_SSO_R33_BCF"),
    "nonsalt": Region("nonsalt", "South Central Nonsalt", "png.nw2_epg0_sno_r33_bcf.w", "NW2_EPG0_SNO_R33_BCF"),
}

ALIASES = {
    "lower_48": "lower48",
    "lower-48": "lower48",
    "south-central": "south_central",
    "southcentral": "south_central",
    "south_central_salt": "salt",
    "south_central_nonsalt": "nonsalt",
}


def resolve_region(value: str) -> Region:
    key = value.strip().lower().replace(" ", "_")
    key = ALIASES.get(key, key)
    try:
        return REGIONS[key]
    except KeyError as exc:
        raise InputError("Unsupported region", region=value, allowed=sorted(REGIONS)) from exc

