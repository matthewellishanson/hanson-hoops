from pathlib import Path

from ingest_br_rookies_2026_into_snapshot import main as ingest_br_rookies
from build_rookie_shooting_snapshot import build_rookie_shooting_stream
from build_rookie_height_stream_long import build_rookie_height_stream_long
from build_rookie_height_stream_wide import build_rookie_height_stream_wide


def main():
    print("=== Ingesting 2026 BR rookies into snapshot ===")
    ingest_br_rookies()

    print("=== Building rookie shooting stream ===")
    build_rookie_shooting_stream()

    print("=== Building rookie height streams (long + wide) ===")
    long_df = build_rookie_height_stream_long()
    build_rookie_height_stream_wide()

    print("Build complete.")


if __name__ == "__main__":
    main()
