"""Regenerate the processed state dataset and statistical output tables."""

from pathlib import Path

from us_crime_analysis.pipeline import run_analysis


def main() -> None:
    paths = run_analysis(
        config_path=Path("config/project.json"),
        source_dir=Path("data/source"),
        processed_dir=Path("data/processed"),
        tables_dir=Path("outputs/tables"),
    )
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
