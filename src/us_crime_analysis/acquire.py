"""Download and normalize the public source snapshots used by the project."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

STATE_CODES_URL = "https://www2.census.gov/geo/docs/reference/state.txt"
ACS_BASE_URL = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/2023/"
    "table-based-SF/data/1YRData"
)
ACS_INCOME_URL = f"{ACS_BASE_URL}/acsdt1y2023-b19013.dat"
ACS_LABOR_URL = f"{ACS_BASE_URL}/acsdt1y2023-b23025.dat"
FBI_URL_TEMPLATE = (
    "https://cde.ucr.cjis.gov/LATEST/summarized/state/{state}/violent-crime"
    "?from=01-2023&to=12-2023"
)
EXCLUDED_GEOGRAPHIES = {"AS", "DC", "GU", "MP", "PR", "UM", "VI"}
USER_AGENT = "us-crime-socioeconomic-analysis/1.0"


@dataclass(frozen=True)
class Download:
    url: str
    body: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


def _download(url: str, timeout: int = 60, attempts: int = 4) -> Download:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                return Download(url=url, body=response.read())
        except (HTTPError, URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def _state_codes(download: Download) -> pd.DataFrame:
    states = pd.read_csv(io.BytesIO(download.body), sep="|", dtype={"STATE": "string"})
    states = states.loc[~states["STUSAB"].isin(EXCLUDED_GEOGRAPHIES)].copy()
    states = states.rename(
        columns={"STATE": "state_fips", "STUSAB": "state_abbr", "STATE_NAME": "state"}
    )
    return states[["state_fips", "state_abbr", "state"]].sort_values("state_abbr")


def _acs_state_rows(download: Download, value_columns: list[str]) -> pd.DataFrame:
    table = pd.read_csv(io.BytesIO(download.body), sep="|", dtype={"GEO_ID": "string"})
    table["state_fips"] = table["GEO_ID"].str.extract(r"^0400000US(\d{2})$")
    return table.dropna(subset=["state_fips"])[["state_fips", *value_columns]]


def _parse_fbi(
    state_abbr: str, state: str, download: Download
) -> tuple[list[dict], str]:
    payload = json.loads(download.body)
    offense_key = f"{state} Offenses"
    counts = payload["offenses"]["actuals"][offense_key]
    rates = payload["offenses"]["rates"][offense_key]
    populations = payload["populations"]["population"][state]
    participating = payload["populations"]["participated_population"][state]
    coverage = payload["tooltips"]["Percent of Population Coverage"][state]

    months = [f"{month:02d}-2023" for month in range(1, 13)]
    if any(counts.get(month) is None for month in months):
        raise ValueError(
            f"{state_abbr}: FBI response does not contain 12 monthly counts"
        )
    if any(
        populations.get(month) is None or participating.get(month) is None
        for month in months
    ):
        raise ValueError(
            f"{state_abbr}: FBI response does not contain 12 population values"
        )
    if any(coverage.get(month) is None for month in months):
        raise ValueError(
            f"{state_abbr}: FBI response does not contain 12 coverage values"
        )

    unique_populations = {int(populations[month]) for month in months}
    if len(unique_populations) != 1:
        raise ValueError(f"{state_abbr}: expected one annual population denominator")

    refresh = (
        payload.get("cde_properties", {}).get("last_refresh_date", {}).get("UCR", "")
    )
    rows = []
    for month in months:
        expected_rate = int(counts[month]) / int(participating[month]) * 100_000
        if abs(float(rates[month]) - expected_rate) > 0.02:
            raise ValueError(
                f"{state_abbr} {month}: CDE rate does not reconcile with participating population"
            )
        rows.append(
            {
                "state_abbr": state_abbr,
                "state": state,
                "month": month,
                "reported_violent_offenses": int(counts[month]),
                "fbi_population": int(populations[month]),
                "participating_population": int(participating[month]),
                "violent_crime_rate_per_100k": float(rates[month]),
                "population_coverage_pct": float(coverage[month]),
                "fbi_source_refresh_date": refresh,
            }
        )
    return (
        rows,
        hashlib.sha256(state_abbr.encode() + b"\0" + download.body).hexdigest(),
    )


def download_sources(output_dir: Path) -> dict[str, Path]:
    """Refresh compact source snapshots from Census and FBI public endpoints."""

    output_dir.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(UTC).replace(microsecond=0).isoformat()

    state_download = _download(STATE_CODES_URL)
    income_download = _download(ACS_INCOME_URL)
    labor_download = _download(ACS_LABOR_URL)

    states = _state_codes(state_download)
    income = _acs_state_rows(income_download, ["B19013_E001"]).rename(
        columns={"B19013_E001": "median_household_income"}
    )
    labor = _acs_state_rows(labor_download, ["B23025_E003", "B23025_E005"]).rename(
        columns={
            "B23025_E003": "civilian_labor_force",
            "B23025_E005": "unemployed",
        }
    )
    acs = states.merge(income, on="state_fips", validate="one_to_one").merge(
        labor, on="state_fips", validate="one_to_one"
    )
    acs["unemployment_rate_pct"] = acs["unemployed"] / acs["civilian_labor_force"] * 100

    state_rows = list(
        states[["state_abbr", "state"]].itertuples(index=False, name=None)
    )

    def fetch_fbi(item: tuple[str, str]) -> tuple[list[dict], str]:
        state_abbr, state = item
        download = _download(FBI_URL_TEMPLATE.format(state=state_abbr))
        return _parse_fbi(state_abbr, state, download)

    with ThreadPoolExecutor(max_workers=6) as executor:
        parsed = list(executor.map(fetch_fbi, state_rows))
    fbi = pd.DataFrame(
        monthly_row for state_rows, _ in parsed for monthly_row in state_rows
    ).sort_values(["state_abbr", "month"])
    fbi_digest = hashlib.sha256(
        "".join(sorted(digest for _, digest in parsed)).encode()
    ).hexdigest()

    state_path = output_dir / "state_codes.csv"
    acs_path = output_dir / "acs_state_2023.csv"
    fbi_path = output_dir / "fbi_reported_violent_crime_2023.csv"
    states.to_csv(
        state_path, index=False, lineterminator="\n", quoting=csv.QUOTE_MINIMAL
    )
    acs.to_csv(acs_path, index=False, lineterminator="\n", float_format="%.8f")
    fbi.to_csv(fbi_path, index=False, lineterminator="\n", float_format="%.8f")

    manifest = pd.DataFrame(
        [
            {
                "source_id": "census_state_codes",
                "publisher": "U.S. Census Bureau",
                "reference_year": "current reference file",
                "access_url": STATE_CODES_URL,
                "retrieved_utc": retrieved,
                "download_sha256": state_download.sha256,
                "artifact": state_path.as_posix(),
                "artifact_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest(),
                "notes": "50 states; District of Columbia and territories excluded",
            },
            {
                "source_id": "acs_b19013",
                "publisher": "U.S. Census Bureau",
                "reference_year": "2023 ACS 1-year",
                "access_url": ACS_INCOME_URL,
                "retrieved_utc": retrieved,
                "download_sha256": income_download.sha256,
                "artifact": acs_path.as_posix(),
                "artifact_sha256": hashlib.sha256(acs_path.read_bytes()).hexdigest(),
                "notes": "B19013_E001 median household income in 2023 dollars",
            },
            {
                "source_id": "acs_b23025",
                "publisher": "U.S. Census Bureau",
                "reference_year": "2023 ACS 1-year",
                "access_url": ACS_LABOR_URL,
                "retrieved_utc": retrieved,
                "download_sha256": labor_download.sha256,
                "artifact": acs_path.as_posix(),
                "artifact_sha256": hashlib.sha256(acs_path.read_bytes()).hexdigest(),
                "notes": "B23025_E003 civilian labor force; B23025_E005 unemployed",
            },
            {
                "source_id": "fbi_cde_violent_crime",
                "publisher": "Federal Bureau of Investigation",
                "reference_year": "2023 monthly UCR submissions",
                "access_url": FBI_URL_TEMPLATE,
                "retrieved_utc": retrieved,
                "download_sha256": fbi_digest,
                "artifact": fbi_path.as_posix(),
                "artifact_sha256": hashlib.sha256(fbi_path.read_bytes()).hexdigest(),
                "notes": "600 state-month rows; CDE rates use each month's participating population",
            },
        ]
    )
    manifest_path = output_dir / "source_manifest.csv"
    manifest.to_csv(manifest_path, index=False, lineterminator="\n")
    return {
        "states": state_path,
        "acs": acs_path,
        "fbi": fbi_path,
        "manifest": manifest_path,
    }
