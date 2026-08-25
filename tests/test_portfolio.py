from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from us_crime_analysis.dashboard import render_dashboard
from us_crime_analysis.pipeline import build_state_analysis, load_config, run_analysis

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "source"


def test_source_snapshot_shape_and_rate_reconciliation() -> None:
    states = pd.read_csv(SOURCE_DIR / "state_codes.csv")
    acs = pd.read_csv(SOURCE_DIR / "acs_state_2023.csv")
    fbi = pd.read_csv(SOURCE_DIR / "fbi_reported_violent_crime_2023.csv")

    assert len(states) == 50
    assert len(acs) == 50
    assert states["state_abbr"].is_unique
    assert acs["state_abbr"].is_unique
    assert len(fbi) == 600
    assert fbi["state_abbr"].nunique() == 50
    assert (fbi.groupby("state_abbr").size() == 12).all()

    expected_rates = (
        fbi["reported_violent_offenses"] / fbi["participating_population"] * 100_000
    )
    assert np.allclose(fbi["violent_crime_rate_per_100k"], expected_rates, atol=0.02)


def test_manifest_artifact_hashes_match() -> None:
    manifest = pd.read_csv(SOURCE_DIR / "source_manifest.csv")
    assert set(manifest["source_id"]) == {
        "census_state_codes",
        "acs_b19013",
        "acs_b23025",
        "fbi_cde_violent_crime",
    }
    for row in manifest.itertuples():
        artifact = ROOT / row.artifact
        assert artifact.exists()
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == row.artifact_sha256


def test_primary_sample_and_documented_exclusions() -> None:
    config = load_config(ROOT / "config" / "project.json")
    data = build_state_analysis(
        SOURCE_DIR / "acs_state_2023.csv",
        SOURCE_DIR / "fbi_reported_violent_crime_2023.csv",
        float(config["minimum_mean_population_coverage_pct"]),
    )
    excluded = set(data.loc[~data["eligible_primary_model"], "state"])

    assert len(data) == 50
    assert int(data["eligible_primary_model"].sum()) == 43
    assert excluded == {
        "Florida",
        "Indiana",
        "Mississippi",
        "Nebraska",
        "New Mexico",
        "South Dakota",
        "Wyoming",
    }


def test_generated_artifacts_are_reproducible(tmp_path: Path) -> None:
    generated = run_analysis(
        config_path=ROOT / "config" / "project.json",
        source_dir=SOURCE_DIR,
        processed_dir=tmp_path / "processed",
        tables_dir=tmp_path / "tables",
    )
    expected = {
        "state_analysis": ROOT / "data" / "processed" / "state_analysis_2023.csv",
        "coefficients": ROOT / "outputs" / "tables" / "model_coefficients.csv",
        "diagnostics": ROOT / "outputs" / "tables" / "model_diagnostics.csv",
        "sensitivity": ROOT / "outputs" / "tables" / "sensitivity_analysis.csv",
        "influence": ROOT / "outputs" / "tables" / "influence_diagnostics.csv",
        "correlations": ROOT / "outputs" / "tables" / "correlations.csv",
        "summary": ROOT / "outputs" / "tables" / "descriptive_summary.csv",
    }
    for key, generated_path in generated.items():
        assert generated_path.read_bytes() == expected[key].read_bytes()

    rendered = render_dashboard(
        state_path=generated["state_analysis"],
        coefficients_path=generated["coefficients"],
        diagnostics_path=generated["diagnostics"],
        correlations_path=generated["correlations"],
        output_path=tmp_path / "portfolio_dashboard.svg",
    )
    assert (
        rendered.read_bytes()
        == (ROOT / "outputs" / "figures" / "portfolio_dashboard.svg").read_bytes()
    )


def test_reported_results_are_locked_to_outputs() -> None:
    coefficients = pd.read_csv(
        ROOT / "outputs" / "tables" / "model_coefficients.csv"
    ).set_index("term")
    diagnostics = pd.read_csv(
        ROOT / "outputs" / "tables" / "model_diagnostics.csv"
    ).iloc[0]
    sensitivity = pd.read_csv(ROOT / "outputs" / "tables" / "sensitivity_analysis.csv")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert diagnostics["sample_size"] == 43
    assert diagnostics["r_squared"] == pytest.approx(0.22143478)
    assert diagnostics["adjusted_r_squared"] == pytest.approx(0.18250651)
    assert coefficients.loc["unemployment_rate_pct", "estimate"] == pytest.approx(
        72.09216092
    )
    assert coefficients.loc["unemployment_rate_pct", "p_value"] == pytest.approx(
        0.00793996
    )
    assert coefficients.loc["median_income_10k", "estimate"] == pytest.approx(
        -32.12369475
    )
    assert coefficients.loc["median_income_10k", "p_value"] == pytest.approx(0.07458916)
    assert len(sensitivity) == 5
    assert (sensitivity["unemployment_estimate"] > 0).all()
    assert (sensitivity["income_estimate"] < 0).all()
    for claim in (
        "72.1 additional",
        "p = 0.0079",
        "32.1 fewer",
        "p = 0.0746",
        "R² = 0.221",
    ):
        assert claim in readme
