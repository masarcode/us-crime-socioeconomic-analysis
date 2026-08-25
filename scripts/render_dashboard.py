"""Render the recruiter-facing SVG dashboard from generated analysis outputs."""

from pathlib import Path

from us_crime_analysis.dashboard import render_dashboard


def main() -> None:
    path = render_dashboard(
        state_path=Path("data/processed/state_analysis_2023.csv"),
        coefficients_path=Path("outputs/tables/model_coefficients.csv"),
        diagnostics_path=Path("outputs/tables/model_diagnostics.csv"),
        correlations_path=Path("outputs/tables/correlations.csv"),
        output_path=Path("outputs/figures/portfolio_dashboard.svg"),
    )
    print(path)


if __name__ == "__main__":
    main()
