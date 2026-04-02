import sqlite3
import os
import logging
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
    _SCRAPE_AVAILABLE = True
except ImportError:
    _SCRAPE_AVAILABLE = False

DB_PATH = os.path.join(os.path.dirname(__file__), "grades.db")

GRADE_VALUES = {
    "A+": 4.3, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D": 1.0, "F": 0.0,
}

# Fallback 2026 prospects used when live scraping is unavailable
FALLBACK_PROSPECTS = [
    # QB
    ("Fernando Mendoza",    "QB",   "Indiana"),
    ("Garrett Nussmeier",   "QB",   "LSU"),
    ("Quinn Ewers",         "QB",   "Texas"),
    # RB
    ("Jeremiyah Love",      "RB",   "Notre Dame"),
    ("TreVeyon Henderson",  "RB",   "Ohio State"),
    ("Kendall Milton",      "RB",   "Georgia"),
    # WR
    ("Elic Ayomanor",       "WR",   "Stanford"),
    ("Emeka Egbuka",        "WR",   "Ohio State"),
    ("Evan Stewart",        "WR",   "Oregon"),
    ("Jalen Royals",        "WR",   "Utah State"),
    # TE
    ("Harold Fannin Jr.",   "TE",   "Bowling Green"),
    ("Oronde Gadsden II",   "TE",   "Syracuse"),
    # OT
    ("Aireontae Ersery",    "OT",   "Minnesota"),
    ("Wyatt Milum",         "OT",   "West Virginia"),
    ("Elijah Arroyo",       "OT",   "Miami"),
    # IOL
    ("Olaivavega Ioane",    "IOL",  "Penn State"),
    ("Donovan Jackson",     "IOL",  "Ohio State"),
    # EDGE
    ("David Bailey",        "EDGE", "Texas Tech"),
    ("Mykel Williams",      "EDGE", "Georgia"),
    ("Princely Umanmielen", "EDGE", "Ole Miss"),
    ("Jack Sawyer",         "EDGE", "Ohio State"),
    # DT
    ("Deone Walker",        "DT",   "Michigan"),
    ("Mason Graham",        "DT",   "Michigan"),
    ("Kenneth Grant",       "DT",   "Michigan"),
    # LB
    ("Arvell Reese",        "LB",   "Ohio State"),
    ("Sonny Styles",        "LB",   "Ohio State"),
    ("Danny Striggow",      "LB",   "Michigan State"),
    # CB
    ("Jahdae Barron",       "CB",   "Texas"),
    ("Benjamin Morrison",   "CB",   "Notre Dame"),
    ("Cobee Bryant",        "CB",   "Kansas"),
    # S
    ("Caleb Downs",         "S",    "Ohio State"),
    ("Xavier Watts",        "S",    "Notre Dame"),
    ("Lathan Ransom",       "S",    "Ohio State"),
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Normalise scraped position abbreviations to app's standard set
_POS_MAP = {
    "OLB": "EDGE", "DE": "EDGE", "DL": "DT", "NT": "DT",
    "ILB": "LB", "MLB": "LB", "G": "IOL", "C": "IOL", "OG": "IOL",
    "OC": "IOL", "FS": "S", "SS": "S", "DB": "CB",
}

VALID_POSITIONS = {"QB", "RB", "WR", "TE", "OT", "IOL", "EDGE", "DT", "LB", "CB", "S"}


def _normalise_pos(raw: str) -> str:
    p = raw.strip().upper()
    return _POS_MAP.get(p, p)


def _scrape_drafttek(year: int = 2026, max_pages: int = 3) -> list:
    """Scrape top prospects from drafttek.com big board.

    drafttek renders plain HTML tables (no JS required), with rows using
    alternating CSS classes TR1/TR2 and columns:
      [rank] [name] [position] [college] ...
    """
    prospects = []
    seen = set()
    base_url = (
        "https://www.drafttek.com/{year}-NFL-Draft-Big-Board/"
        "Top-NFL-Draft-Prospects-{year}-Page-{page}.asp"
    )
    for page in range(1, max_pages + 1):
        url = base_url.format(year=year, page=page)
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
        except Exception as exc:
            logging.warning("drafttek page %d fetch failed: %s", page, exc)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        for row in soup.find_all("tr", class_=lambda c: c and c.upper().startswith("TR")):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            name = cells[1].get_text(strip=True)
            pos_raw = cells[2].get_text(strip=True)
            college = cells[3].get_text(strip=True)
            if not name or not pos_raw or not college:
                continue
            pos = _normalise_pos(pos_raw)
            if pos not in VALID_POSITIONS:
                continue
            key = name.lower()
            if key not in seen:
                seen.add(key)
                prospects.append((name, pos, college))

    return prospects


def fetch_prospects(year: int = 2026) -> list:
    """Return (name, position, college) tuples for draft prospects.

    Tries live scraping from drafttek.com first; falls back to the
    built-in 2026 prospect list if scraping fails or returns too few results.
    """
    if not _SCRAPE_AVAILABLE:
        logging.info("requests/beautifulsoup4 not installed — using fallback prospects")
        return FALLBACK_PROSPECTS

    scraped = _scrape_drafttek(year)
    if len(scraped) >= 20:
        logging.info("Loaded %d prospects from drafttek.com", len(scraped))
        return scraped

    logging.warning(
        "Scraping returned %d prospects (expected >= 20) — using fallback list",
        len(scraped),
    )
    return FALLBACK_PROSPECTS


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
            prospects = fetch_prospects()
            conn.executemany(
                "INSERT INTO players (name, position, college) VALUES (?, ?, ?)",
                prospects,
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
