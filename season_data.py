"""Validate one complete season and query it as a team-per-match SQLite view."""

import argparse
import csv
from datetime import datetime
from io import StringIO
from pathlib import Path
import sqlite3
from tempfile import NamedTemporaryFile
from urllib.request import Request, urlopen

SEASON = "2025–26"
SOURCE = "https://www.football-data.co.uk/mmz4281/2526/E0.csv"
ARCHIVE = "https://www.football-data.co.uk/englandm.php"
LOCAL_CSV = Path(__file__).with_name("season-2025-26.csv")
VENUES = ("All matches", "Home", "Away")
CLUB_NAMES = {
    "Brighton": "Brighton & Hove Albion", "Leeds": "Leeds United",
    "Man City": "Manchester City", "Man United": "Manchester United",
    "Newcastle": "Newcastle United", "Nott'm Forest": "Nottingham Forest",
    "Tottenham": "Tottenham Hotspur", "West Ham": "West Ham United",
    "Wolves": "Wolverhampton Wanderers",
}
CLUBS = frozenset({
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Burnley",
    "Chelsea", "Crystal Palace", "Everton", "Fulham", "Leeds", "Liverpool",
    "Man City", "Man United", "Newcastle", "Nott'm Forest", "Sunderland",
    "Tottenham", "West Ham", "Wolves",
})
FIELDS = ("Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "HS", "AS", "HST", "AST")
SCHEMA = """
CREATE TABLE matches (
    date TEXT NOT NULL, home TEXT NOT NULL, away TEXT NOT NULL,
    home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL,
    home_shots INTEGER NOT NULL, away_shots INTEGER NOT NULL,
    home_on_target INTEGER NOT NULL, away_on_target INTEGER NOT NULL,
    PRIMARY KEY (home, away)
);
CREATE VIEW perspectives
    (date, club, opponent, venue, gf, ga, shots, shots_against, target, target_against) AS
    SELECT date, home, away, 'Home', home_goals, away_goals,
           home_shots, away_shots, home_on_target, away_on_target FROM matches
    UNION ALL
    SELECT date, away, home, 'Away', away_goals, home_goals,
           away_shots, home_shots, away_on_target, home_on_target FROM matches;
CREATE VIEW club_matches AS
    SELECT *,
           CASE WHEN gf > ga THEN 'W' WHEN gf = ga THEN 'D' ELSE 'L' END AS result,
           CASE WHEN gf > ga THEN 3 WHEN gf = ga THEN 1 ELSE 0 END AS points
    FROM perspectives;
"""


def club_name(source_name):
    return CLUB_NAMES.get(source_name, source_name)


def download_season():
    """Fetch the season CSV with a bounded request and response size."""
    request = Request(SOURCE, headers={"User-Agent": "Premier League Analytics/1.0"})
    limit = 2_000_000
    with urlopen(request, timeout=15) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("The downloaded file is larger than the expected season CSV.")
    return raw


def parse_season(raw):
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    if not set(FIELDS).issubset(reader.fieldnames or ()):
        raise ValueError("The CSV must contain match dates, teams, goals, shots and shots on target.")

    matches = []
    fixtures = set()
    dates_by_club = set()
    for row in reader:
        if not any(row.get(field) for field in FIELDS):
            continue
        try:
            date = datetime.strptime(row["Date"], "%d/%m/%Y").date().isoformat()
            home, away = row["HomeTeam"].strip(), row["AwayTeam"].strip()
            counts = tuple(int(row[column]) for column in FIELDS[3:])
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid date, team or match statistic on CSV row {reader.line_num}.") from exc
        if not ("2025-08-01" <= date <= "2026-05-31") or row.get("Div", "E0") != "E0":
            raise ValueError("The file must contain 2025–26 Premier League results.")
        if home not in CLUBS or away not in CLUBS or home == away:
            raise ValueError(f"Unexpected fixture on CSV row {reader.line_num}.")
        if min(counts) < 0 or counts[4] > counts[2] or counts[5] > counts[3]:
            raise ValueError(f"Inconsistent shot or goal counts on CSV row {reader.line_num}.")
        if (home, away) in fixtures or {(date, home), (date, away)} & dates_by_club:
            raise ValueError(f"Duplicate fixture or club match date on CSV row {reader.line_num}.")
        fixtures.add((home, away))
        dates_by_club.update(((date, home), (date, away)))
        matches.append((date, club_name(home), club_name(away), *counts))

    expected = {(home, away) for home in CLUBS for away in CLUBS if home != away}
    if fixtures != expected:
        raise ValueError(f"Expected all 380 fixtures. The file contains {len(fixtures)} valid fixtures.")
    return matches


def query_season(matches):
    """Build league aggregates and ordered match logs for each venue filter."""
    league, logs = {}, {}
    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
        db.executemany("INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", matches)
        for venue in VENUES:
            league[venue] = [dict(row) for row in db.execute("""
                SELECT club, COUNT(*) AS played, SUM(result = 'W') AS wins,
                       SUM(result = 'D') AS draws, SUM(result = 'L') AS losses,
                       SUM(points) AS points, AVG(points) AS ppg,
                       AVG(gf) AS gf, AVG(ga) AS ga, AVG(shots) AS shots,
                       AVG(shots_against) AS shots_against, AVG(target) AS target,
                       AVG(target_against) AS target_against
                FROM club_matches WHERE (? = 'All matches' OR venue = ?)
                GROUP BY club
                ORDER BY ppg DESC, SUM(gf - ga) DESC, SUM(gf) DESC, club
            """, (venue, venue))]
            logs[venue] = {row["club"]: [] for row in league[venue]}
            for row in db.execute("""
                SELECT * FROM club_matches WHERE (? = 'All matches' OR venue = ?)
                ORDER BY date, opponent
            """, (venue, venue)):
                logs[venue][row["club"]].append(dict(row))
    return league, logs


def main():
    parser = argparse.ArgumentParser(description="Import the 2025–26 Premier League CSV.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--download", action="store_true", help="Fetch the CSV from Football-Data.co.uk.")
    mode.add_argument("--file", type=Path, help="Use a previously downloaded Football-Data CSV.")
    args = parser.parse_args()
    try:
        raw = download_season() if args.download else args.file.read_bytes()
        matches = parse_season(raw)
        with NamedTemporaryFile(dir=LOCAL_CSV.parent, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
        try:
            temporary.write_bytes(raw)
            temporary.replace(LOCAL_CSV)
        finally:
            temporary.unlink(missing_ok=True)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print(f"Validated {len(matches)} matches across {len(CLUBS)} clubs.")


if __name__ == "__main__":
    main()
