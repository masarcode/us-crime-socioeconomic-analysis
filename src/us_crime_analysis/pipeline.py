"""Validated preparation, regression, diagnostics, and reporting tables."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import jarque_bera

EXPECTED_STATE_COUNT = 50
MODEL_TERMS = ["const", "unemployment_rate_pct", "median_income_10k"]


@dataclass
class ModelBundle:
    data: pd.DataFrame
    model: object
    classical_model: object
    outcome: str
    coverage_floor: float
    excluded_states: tuple[str, ...]


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if int(config["analysis_year"]) != 2023:
        raise ValueError("This portfolio snapshot is configured for 2023")
    threshold = float(config["minimum_mean_population_coverage_pct"])
    if not 0 <= threshold <= 100:
        raise ValueError("Coverage threshold must be between 0 and 100")
    return config


def _require_columns(frame: pd.DataFrame, columns: set[str], source: str) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise ValueError(f"{source} is missing columns: {sorted(missing)}")


def build_state_analysis(
    acs_path: Path, fbi_path: Path, coverage_threshold: float
) -> pd.DataFrame:
    """Join direct state estimates and flag the documented modeling sample."""

    acs = pd.read_csv(acs_path, dtype={"state_fips": "string"})
    fbi = pd.read_csv(fbi_path)
    _require_columns(
        acs,
        {
            "state_fips",
            "state_abbr",
            "state",
            "median_household_income",
            "civilian_labor_force",
            "unemployed",
            "unemployment_rate_pct",
        },
        "ACS source",
    )
    _require_columns(
        fbi,
        {
            "state_abbr",
            "state",
            "month",
            "reported_violent_offenses",
            "fbi_population",
            "participating_population",
            "violent_crime_rate_per_100k",
            "population_coverage_pct",
        },
        "FBI source",
    )

    if len(acs) != EXPECTED_STATE_COUNT or acs["state_abbr"].duplicated().any():
        raise ValueError("ACS source must contain exactly 50 unique states")
    if len(fbi) != EXPECTED_STATE_COUNT * 12:
        raise ValueError(
            "FBI source must contain 12 monthly rows for each of 50 states"
        )
    if fbi[["state_abbr", "month"]].duplicated().any():
        raise ValueError("FBI source contains duplicate state-month rows")
    if not (fbi.groupby("state_abbr").size() == 12).all():
        raise ValueError("FBI source does not contain 12 months for every state")
    expected_monthly_rates = (
        fbi["reported_violent_offenses"] / fbi["participating_population"] * 100_000
    )
    if not np.allclose(
        fbi["violent_crime_rate_per_100k"], expected_monthly_rates, atol=0.02
    ):
        raise ValueError(
            "Monthly FBI rates do not reconcile with participating populations"
        )

    fbi_states = fbi[["state_abbr", "state"]].drop_duplicates()
    if len(fbi_states) != EXPECTED_STATE_COUNT:
        raise ValueError("FBI source must contain exactly 50 unique states")
    if not (fbi.groupby("state_abbr")["fbi_population"].nunique() == 1).all():
        raise ValueError("FBI annual population changed within the analysis year")

    fbi_annual = fbi.groupby(["state_abbr", "state"], as_index=False).agg(
        reported_violent_offenses=("reported_violent_offenses", "sum"),
        fbi_population=("fbi_population", "first"),
        mean_participating_population=("participating_population", "mean"),
        violent_crime_rate_per_100k=("violent_crime_rate_per_100k", "sum"),
        mean_population_coverage_pct=("population_coverage_pct", "mean"),
        min_population_coverage_pct=("population_coverage_pct", "min"),
        fbi_source_refresh_date=("fbi_source_refresh_date", "first"),
    )

    data = acs.merge(
        fbi_annual,
        on="state_abbr",
        validate="one_to_one",
        suffixes=("_acs", "_fbi"),
    )
    if len(data) != EXPECTED_STATE_COUNT:
        raise ValueError("ACS and FBI sources did not match all 50 states")
    if not data["state_acs"].equals(data["state_fbi"]):
        raise ValueError("State names differ between ACS and FBI sources")

    expected_unemployment = data["unemployed"] / data["civilian_labor_force"] * 100
    if not np.allclose(data["unemployment_rate_pct"], expected_unemployment, atol=1e-7):
        raise ValueError("Stored unemployment rates do not reconcile with ACS counts")
    if (data["violent_crime_rate_per_100k"] <= 0).any():
        raise ValueError("Annualized FBI rates must be positive")
    if data["mean_population_coverage_pct"].notna().sum() != EXPECTED_STATE_COUNT:
        raise ValueError("FBI coverage is missing for one or more states")

    data = data.rename(columns={"state_acs": "state"}).drop(columns="state_fbi")
    data["median_income_10k"] = data["median_household_income"] / 10_000
    data["eligible_primary_model"] = (
        data["mean_population_coverage_pct"] >= coverage_threshold
    )
    data["exclusion_reason"] = np.where(
        data["eligible_primary_model"],
        "",
        f"Mean FBI reporting coverage below {coverage_threshold:.0f}%",
    )
    ordered = [
        "state_fips",
        "state_abbr",
        "state",
        "reported_violent_offenses",
        "fbi_population",
        "mean_participating_population",
        "violent_crime_rate_per_100k",
        "mean_population_coverage_pct",
        "min_population_coverage_pct",
        "median_household_income",
        "civilian_labor_force",
        "unemployed",
        "unemployment_rate_pct",
        "median_income_10k",
        "eligible_primary_model",
        "exclusion_reason",
        "fbi_source_refresh_date",
    ]
    return data[ordered].sort_values("state").reset_index(drop=True)


def fit_model(
    data: pd.DataFrame,
    coverage_floor: float,
    *,
    log_outcome: bool = False,
    excluded_states: tuple[str, ...] = (),
) -> ModelBundle:
    sample = data.loc[
        (data["mean_population_coverage_pct"] >= coverage_floor)
        & ~data["state_abbr"].isin(excluded_states)
    ].copy()
    if len(sample) < 10:
        raise ValueError("Model requires at least 10 states")

    outcome = "log_violent_crime_rate" if log_outcome else "violent_crime_rate_per_100k"
    y = (
        np.log(sample["violent_crime_rate_per_100k"])
        if log_outcome
        else sample[outcome]
    )
    x = sm.add_constant(sample[["unemployment_rate_pct", "median_income_10k"]])
    classical = sm.OLS(y, x).fit()
    robust = sm.OLS(y, x).fit(cov_type="HC3")
    return ModelBundle(
        data=sample,
        model=robust,
        classical_model=classical,
        outcome=outcome,
        coverage_floor=coverage_floor,
        excluded_states=excluded_states,
    )


def coefficient_table(bundle: ModelBundle) -> pd.DataFrame:
    intervals = bundle.model.conf_int(alpha=0.05)
    units = {
        "const": "baseline intercept",
        "unemployment_rate_pct": "per 1 percentage-point increase",
        "median_income_10k": "per $10,000 increase",
    }
    return pd.DataFrame(
        {
            "term": MODEL_TERMS,
            "estimate": [bundle.model.params[term] for term in MODEL_TERMS],
            "robust_standard_error": [bundle.model.bse[term] for term in MODEL_TERMS],
            "p_value": [bundle.model.pvalues[term] for term in MODEL_TERMS],
            "ci_95_lower": [intervals.loc[term, 0] for term in MODEL_TERMS],
            "ci_95_upper": [intervals.loc[term, 1] for term in MODEL_TERMS],
            "unit": [units[term] for term in MODEL_TERMS],
            "covariance": "HC3",
        }
    )


def model_diagnostics(bundle: ModelBundle) -> pd.DataFrame:
    model = bundle.classical_model
    influence = model.get_influence().summary_frame()
    jb_stat, jb_p, skew, kurtosis = jarque_bera(model.resid)
    bp_stat, bp_p, _, _ = het_breuschpagan(model.resid, model.model.exog)
    x = model.model.exog
    vif_unemployment = variance_inflation_factor(x, 1)
    vif_income = variance_inflation_factor(x, 2)
    return pd.DataFrame(
        [
            {
                "sample_size": int(model.nobs),
                "outcome": bundle.outcome,
                "coverage_floor_pct": bundle.coverage_floor,
                "excluded_states": ";".join(bundle.excluded_states),
                "r_squared": model.rsquared,
                "adjusted_r_squared": model.rsquared_adj,
                "rmse": float(np.sqrt(np.mean(np.square(model.resid)))),
                "condition_number": model.condition_number,
                "jarque_bera_stat": jb_stat,
                "jarque_bera_p_value": jb_p,
                "residual_skew": skew,
                "residual_kurtosis": kurtosis,
                "breusch_pagan_stat": bp_stat,
                "breusch_pagan_p_value": bp_p,
                "unemployment_vif": vif_unemployment,
                "income_vif": vif_income,
                "max_cooks_distance": influence["cooks_d"].max(),
                "cooks_flag_threshold": 4 / model.nobs,
            }
        ]
    )


def influence_table(bundle: ModelBundle) -> pd.DataFrame:
    influence = (
        bundle.classical_model.get_influence().summary_frame().reset_index(drop=True)
    )
    result = bundle.data[["state", "state_abbr"]].reset_index(drop=True).copy()
    result["cooks_distance"] = influence["cooks_d"]
    result["leverage"] = influence["hat_diag"]
    result["studentized_residual"] = influence["student_resid"]
    result["flagged_cooks_distance"] = result["cooks_distance"] > 4 / len(result)
    return result.sort_values("cooks_distance", ascending=False).reset_index(drop=True)


def _sensitivity_row(name: str, bundle: ModelBundle) -> dict:
    model = bundle.model
    return {
        "scenario": name,
        "sample_size": int(model.nobs),
        "outcome": bundle.outcome,
        "coverage_floor_pct": bundle.coverage_floor,
        "excluded_states": ";".join(bundle.excluded_states),
        "r_squared": bundle.classical_model.rsquared,
        "adjusted_r_squared": bundle.classical_model.rsquared_adj,
        "unemployment_estimate": model.params["unemployment_rate_pct"],
        "unemployment_p_value": model.pvalues["unemployment_rate_pct"],
        "income_estimate": model.params["median_income_10k"],
        "income_p_value": model.pvalues["median_income_10k"],
    }


def run_analysis(
    *,
    config_path: Path,
    source_dir: Path,
    processed_dir: Path,
    tables_dir: Path,
) -> dict[str, Path]:
    """Build the analysis dataset and all deterministic reporting tables."""

    config = load_config(config_path)
    threshold = float(config["minimum_mean_population_coverage_pct"])
    data = build_state_analysis(
        source_dir / "acs_state_2023.csv",
        source_dir / "fbi_reported_violent_crime_2023.csv",
        threshold,
    )
    primary = fit_model(data, threshold)
    influence = influence_table(primary)
    influential_states = tuple(influence.head(2)["state_abbr"])

    scenarios = [
        ("primary", primary),
        ("all_50_states", fit_model(data, 0)),
        ("95_pct_coverage", fit_model(data, 95)),
        ("log_outcome", fit_model(data, threshold, log_outcome=True)),
        (
            "exclude_two_most_influential",
            fit_model(data, threshold, excluded_states=influential_states),
        ),
    ]
    sensitivity = pd.DataFrame(
        _sensitivity_row(name, model) for name, model in scenarios
    )

    eligible = primary.data
    correlations = eligible[
        [
            "violent_crime_rate_per_100k",
            "unemployment_rate_pct",
            "median_household_income",
        ]
    ].corr()
    correlations.index.name = "variable"
    summary = (
        eligible[
            [
                "violent_crime_rate_per_100k",
                "unemployment_rate_pct",
                "median_household_income",
                "mean_population_coverage_pct",
            ]
        ]
        .describe()
        .transpose()
    )
    summary.index.name = "variable"

    processed_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "state_analysis": processed_dir / "state_analysis_2023.csv",
        "coefficients": tables_dir / "model_coefficients.csv",
        "diagnostics": tables_dir / "model_diagnostics.csv",
        "sensitivity": tables_dir / "sensitivity_analysis.csv",
        "influence": tables_dir / "influence_diagnostics.csv",
        "correlations": tables_dir / "correlations.csv",
        "summary": tables_dir / "descriptive_summary.csv",
    }
    data.to_csv(
        paths["state_analysis"], index=False, float_format="%.8f", lineterminator="\n"
    )
    coefficient_table(primary).to_csv(
        paths["coefficients"], index=False, float_format="%.8f", lineterminator="\n"
    )
    model_diagnostics(primary).to_csv(
        paths["diagnostics"], index=False, float_format="%.8f", lineterminator="\n"
    )
    sensitivity.to_csv(
        paths["sensitivity"], index=False, float_format="%.8f", lineterminator="\n"
    )
    influence.to_csv(
        paths["influence"], index=False, float_format="%.8f", lineterminator="\n"
    )
    correlations.to_csv(paths["correlations"], float_format="%.8f", lineterminator="\n")
    summary.to_csv(paths["summary"], float_format="%.8f", lineterminator="\n")
    return paths
