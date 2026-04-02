import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "grades.db")

GRADE_VALUES = {
    "A+": 4.3, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D": 1.0, "F": 0.0,
}

PROSPECTS = [
    ("Cam Ward",           "QB",   "Miami"),
    ("Shedeur Sanders",    "QB",   "Colorado"),
    ("Dillon Gabriel",     "QB",   "Oregon"),
    ("Travis Hunter",      "WR",   "Colorado"),
    ("Tetairoa McMillan",  "WR",   "Arizona"),
    ("Luther Burden III",  "WR",   "Missouri"),
    ("Matthew Golden",     "WR",   "Texas"),
    ("Ashton Jeanty",      "RB",   "Boise State"),
    ("Omarion Hampton",    "RB",   "North Carolina"),
    ("Tyler Warren",       "TE",   "Penn State"),
    ("Colston Loveland",   "TE",   "Michigan"),
    ("Will Campbell",      "OT",   "LSU"),
    ("Kelvin Banks Jr.",   "OT",   "Texas"),
    ("Josh Simmons",       "OT",   "Ohio State"),
    ("Tyler Booker",       "IOL",  "Alabama"),
    ("Abdul Carter",       "EDGE", "Penn State"),
    ("James Pearce Jr.",   "EDGE", "Tennessee"),
    ("Jalon Walker",       "EDGE", "Georgia"),
    ("Mike Green",         "EDGE", "Marshall"),
    ("Mason Graham",       "DT",   "Michigan"),
    ("Kenneth Grant",      "DT",   "Michigan"),
    ("Darius Alexander",   "DT",   "Toledo"),
    ("Jihaad Campbell",    "LB",   "Alabama"),
    ("Nick Emmanwori",     "LB",   "South Carolina"),
    ("Will Johnson",       "CB",   "Michigan"),
    ("Jahdae Barron",      "CB",   "Texas"),
    ("Trey Amos",          "CB",   "Ole Miss"),
    ("Malaki Starks",      "S",    "Georgia"),
    ("Kristian Story",     "S",    "Alabama"),
]


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                position  TEXT NOT NULL,
                college   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS grades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id   INTEGER NOT NULL REFERENCES players(id),
                username    TEXT NOT NULL,
                grade       TEXT NOT NULL,
                submitted_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS uq_user_player
                ON grades(player_id, username);
        """)

        if conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO players (name, position, college) VALUES (?, ?, ?)",
                PROSPECTS,
            )


def get_all_players():
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, name, position, college FROM players ORDER BY position, name"
        ).fetchall()


def get_player_stats(player_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT grade FROM grades WHERE player_id = ?", (player_id,)
        ).fetchall()

    if not rows:
        return 0, None, {}

    dist = {}
    total = 0.0
    for (g,) in rows:
        dist[g] = dist.get(g, 0) + 1
        total += GRADE_VALUES.get(g, 0)

    avg = total / len(rows)
    return len(rows), avg, dist


def numeric_to_letter(value: float) -> str:
    closest = min(GRADE_VALUES, key=lambda g: abs(GRADE_VALUES[g] - value))
    return closest


def submit_grade(player_id: int, username: str, grade: str) -> bool:
    if grade not in GRADE_VALUES:
        return False
    ts = datetime.utcnow().isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO grades (player_id, username, grade, submitted_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(player_id, username) DO UPDATE
                   SET grade = excluded.grade, submitted_at = excluded.submitted_at""",
                (player_id, username.strip(), grade, ts),
            )
        return True
    except Exception:
        return False


def get_user_grade(player_id: int, username: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT grade FROM grades WHERE player_id = ? AND username = ?",
            (player_id, username.strip()),
        ).fetchone()
    return row[0] if row else None


def get_leaderboard():
    players = get_all_players()
    rows = []
    for pid, name, pos, college in players:
        count, avg, _ = get_player_stats(pid)
        if count > 0:
            rows.append((name, pos, college, count, numeric_to_letter(avg), avg))
    rows.sort(key=lambda r: r[5], reverse=True)
    return [(n, p, c, cnt, ltr) for n, p, c, cnt, ltr, _ in rows]
