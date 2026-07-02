import requests
from bs4 import BeautifulSoup
import json, time, re
from datetime import datetime

BASE = "https://www.hockeyvictoria.org.au"

# The team whose results we want, identified by CLUB NAME in the team link text.
CLUB = "Essendon Hockey"

# Grades Essendon Hockey plays in, as "season_id/grade_id" pairs.
# Add every grade you want on the page.
COMPETITIONS = [
    ("25879/42158", "Womens Premier League"),
    ("25879/42156", "Mens Premier League"),
    ("25879/42258", "Womens Premier League Reserves"),
    ("25879/42243", "Mens Premier League Reserves"),
    ("25879/42239", "Mens Pennant D North West"),
    ("25879/42241", "Mens Pennant E North West"),
    ("25879/42251", "Womens Pennant A"),
    ("25879/42254", "Womens Pennant D North West"),
    ("25879/42256", "Womens Pennant E North West"),
    ("25879/42249", "Womens Metro 1 North West"),
]

# Stop walking rounds after this many consecutive empty/missing rounds.
MAX_EMPTY_ROUNDS = 3
MAX_ROUNDS = 40  # hard safety cap

def fetch(url):
    r = requests.get(url, timeout=25, headers={"User-Agent": "essendon-results-bot"})
    r.raise_for_status()
    return r.text

def parse_round(comp_path, round_no):
    """Return (heading, list_of_games) for one round, or (None, []) if empty."""
    url = f"{BASE}/games/{comp_path}/round/{round_no}"
    try:
        html = fetch(url)
    except Exception:
        return None, []

    soup = BeautifulSoup(html, "html.parser")

    # Grade heading, e.g. "2026 Senior Competition · Womens Premier League - 2026 · Round 1"
    heading = ""
    h = soup.find(["h1", "h2", "h3"], string=re.compile("Round", re.I))
    if h:
        heading = h.get_text(" ", strip=True)

    games = []
    # Each game has two team links: /games/team/{season}/{teamid}
    team_links = soup.select("a[href*='/games/team/']")

    # Walk team links in pairs (home, away). The score sits in the text between them.
    # More robust: find each game's Details link and work outward.
    detail_links = soup.select("a[href*='/game/']")

    for dl in detail_links:
        # Climb up to the container holding this game's block
        container = dl.find_parent()
        for _ in range(6):  # climb a few levels to capture both teams
            if container and len(container.select("a[href*='/games/team/']")) >= 2:
                break
            container = container.find_parent() if container else None
        if not container:
            continue

        teams = container.select("a[href*='/games/team/']")
        if len(teams) < 2:
            continue

        home = teams[0].get_text(strip=True)
        away = teams[1].get_text(strip=True)

        # Only keep games involving our club
        if CLUB.lower() not in (home + " " + away).lower():
            continue

        # Score: look for a pattern like "4 - 4" in the container text
        ctext = container.get_text(" ", strip=True)
        m = re.search(r"(\d+)\s*-\s*(\d+)", ctext)
        score = f"{m.group(1)}-{m.group(2)}" if m else ""

        # Date/time: first date-like token
        dm = re.search(r"([A-Z][a-z]{2}\s+\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})", ctext)
        date = dm.group(1) if dm else ""
        tm = re.search(r"\b(\d{1,2}:\d{2})\b", ctext)
        gtime = tm.group(1) if tm else ""

        game_id = dl.get("href", "").rstrip("/").split("/")[-1]

        games.append({
            "game_id": game_id,
            "home": home,
            "away": away,
            "score": score,
            "date": date,
            "time": gtime,
            "played": bool(score),
        })

    # De-dupe by game_id
    seen, unique = set(), []
    for g in games:
        if g["game_id"] and g["game_id"] not in seen:
            seen.add(g["game_id"])
            unique.append(g)
    return heading, unique

def scrape_grade(comp_path, label):
    rounds = {}
    empty_streak = 0
    for rn in range(1, MAX_ROUNDS + 1):
        heading, games = parse_round(comp_path, rn)
        # A round "exists" if the page had any team links at all for our club-bearing games,
        # OR the heading was found. We only store rounds with our games.
        if games:
            rounds[str(rn)] = games
            empty_streak = 0
        else:
            empty_streak += 1
            if empty_streak >= MAX_EMPTY_ROUNDS and rounds:
                break
        time.sleep(1)  # be polite to the server
    return rounds

def main():
    data = {"updated": datetime.now().isoformat(timespec="minutes"), "grades": []}
    for comp_path, label in COMPETITIONS:
        print(f"Scanning {label} ({comp_path})...")
        try:
            rounds = scrape_grade(comp_path, label)
        except Exception as e:
            print(f"  {label} failed: {e}")
            rounds = {}
        data["grades"].append({"label": label, "rounds": rounds})
        print(f"  Found {sum(len(v) for v in rounds.values())} games across {len(rounds)} rounds")

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved results.json — updated {data['updated']}")

if __name__ == "__main__":
    main()
