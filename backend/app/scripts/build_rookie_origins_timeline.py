import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

SPECIAL_ORIGINS = {"International", "US (no college)", "US Total"}


def parse_end_year(season):
    if not season:
        return None
    match = re.match(r"(\d{4})-(\d{2})", str(season).strip())
    if not match:
        return None
    start_year = int(match.group(1))
    end_two = int(match.group(2))
    end_year = (start_year // 100) * 100 + end_two
    if end_year < start_year:
        end_year += 100
    return end_year


def detect_country_key(fieldnames):
    for name in fieldnames:
        lower = name.lower()
        if "country" in lower or "nationality" in lower:
            return name
    return None


def is_us(value):
    if not value:
        return False
    normalized = str(value).strip().lower()
    return normalized in {
        "usa",
        "us",
        "u.s.",
        "u.s.a.",
        "united states",
        "united states of america",
        "america",
    }


def classify_origin(row, country_key):
    college = (row.get("College") or "").strip()
    if college:
        return college
    if country_key:
        country = (row.get(country_key) or "").strip()
        if country and not is_us(country):
            return "International"
        return "US (no college)"
    return "International"


def build_counts(rows, country_key):
    counts = defaultdict(lambda: defaultdict(int))
    for row in rows:
        season_year = parse_end_year(row.get("Season", ""))
        if not season_year:
            continue
        origin = classify_origin(row, country_key)
        counts[season_year][origin] += 1
    return counts


def write_output(counts, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["season", "origin", "count"])
        for season in sorted(counts):
            per_season = counts[season]
            us_total = sum(
                count for origin, count in per_season.items() if origin != "International"
            )
            if us_total:
                per_season["US Total"] = us_total
            specials = [
                (name, per_season[name])
                for name in ("International", "US (no college)", "US Total")
                if name in per_season
            ]
            colleges = [
                (origin, count)
                for origin, count in per_season.items()
                if origin not in SPECIAL_ORIGINS
            ]
            colleges.sort(key=lambda item: (-item[1], item[0]))
            ranked = colleges[:8] + specials
            ranked.sort(key=lambda item: (-item[1], item[0]))
            for origin, count in ranked:
                writer.writerow([season, origin, count])


def main():
    parser = argparse.ArgumentParser(description="Build rookie origin timeline CSV for the bar chart race.")
    parser.add_argument(
        "--input",
        default=r"C:\Users\mehan\Documents\Basketball\hanson-hoops\backend\docs\data\BR_Origins_All_Raw.csv",
        help="Path to BR_Origins_All_Raw.csv",
    )
    parser.add_argument(
        "--output",
        default=r"C:\Users\mehan\Documents\matthewellishanson.github.io\hanson-hoops\rookies\data\rookie_origins_timeline.csv",
        help="Output path for rookie_origins_timeline.csv",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    with input_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Input CSV is missing headers.")
        country_key = detect_country_key(reader.fieldnames)
        counts = build_counts(reader, country_key)

    write_output(counts, output_path)


if __name__ == "__main__":
    main()
