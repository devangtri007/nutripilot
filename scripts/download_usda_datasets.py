#!/usr/bin/env python3
"""Download official USDA FoodData Central bulk datasets.

The URLs below are pinned to the releases documented by USDA at the time this
package was built. Check the USDA download page before a future refresh because
release numbers and URLs can change.
"""
import argparse
from pathlib import Path
import requests

DATASETS = {
    "foundation": "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_csv_2026-04-30.zip",
    "fndds": "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_survey_food_csv_2024-10-31.zip",
    "branded": "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_branded_food_csv_2026-04-30.zip",
}


def download(name, output_dir):
    url = DATASETS[name]
    out = output_dir / Path(url).name
    output_dir.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with out.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    print(f"Downloaded {name}: {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["foundation", "fndds", "branded", "all"], default="foundation")
    parser.add_argument("--output-dir", default="data/raw")
    args = parser.parse_args()
    if args.dataset == "all":
        names = list(DATASETS)
    else:
        names = [args.dataset]
    for name in names:
        download(name, Path(args.output_dir))


if __name__ == "__main__":
    main()
