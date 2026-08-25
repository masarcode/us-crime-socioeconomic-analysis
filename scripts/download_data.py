"""Refresh the compact, documented source snapshots from public endpoints."""

from pathlib import Path

from us_crime_analysis.acquire import download_sources


def main() -> None:
    paths = download_sources(Path("data/source"))
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
