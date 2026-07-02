import requests
from bs4 import BeautifulSoup
import json, time, re
from datetime import datetime

BASE = "https://www.hockeyvictoria.org.au"
CLUB = "Essendon Hockey"

COMPETITIONS = [  
    ("25879/42156", "Mens Premier League"),
    ("25879/42243", "Mens Premier League Reserves"),
    ("25879/42239", "Mens Pennant D North West"),
    ("25879/42241", "Mens Pennant E North West"),
    ("25879/42158", "Womens Premier League"),
    ("25879/42258", "Womens Premier League Reserves"),
    ("25879/42251", "Womens Pennant A"),
    ("25879/42254", "Womens Pennant D North West"),
    ("25879/42256", "Womens Pennant E North West"),
    ("25879/42249", "Womens Metro 1 North West"),
    ("26185/42434", "2026 Midweek Mens Open NW"),
    ("26185/42441", "2026 Midweek Mens 40+ NW"),
    ("26185/42444", "2026 Midweek Mens 50+ NW"),
    ("26185/42451", "2026 Midweek Womens 45+"),
]

MAX_EMPTY_ROUNDS = 3
MAX_ROUNDS = 40

MONTHS = {m: i for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], start=1)}

def fetch(url):
    r = requests.get(url, timeout=25, headers={"User-Agent": "essendon-results-bot"})
    r.raise_for_status()
    return r.text

def parse_date(text):
    """Find a date like 'Sat 05 Apr 2026' and return ISO 'YYYY-MM-DD', or ''."""
    m = re.search(r"\b(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{4})", text)
    if m:
        day, mon, year = int(m.group(1)), m.group(2), int(m.group(3))
        if mon in MONTHS:
            return f"{year:04d}-{MONTHS[mon]:02d}-{day:02d}"
    return ""

def parse_round(comp_path, round_no):
    url = f"{BASE}/games/{comp_path}/round/{round_no}"
    try:
        html = fetch(url)
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    detail_links = soup.select("a[href*='/game/']")
    games = []

    for dl in detail_links:
        container = dl.find_parent()
        for _ in range(6):
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
        if CLUB.lower() not in (home + " " + away).lower():
            continue

        ctext = container.get_text(" ", strip=True)
        sm = re.search(r"(\d+)\s*-\s*(\d+)", ctext)
        score = f"{sm.group(1)}-{sm.group(2)}" if sm else ""
        iso_date = parse_date(ctext)
        tm = re.search(r"\b(\d{1,2}:\d{2})\b", ctext)
        gtime = tm.group(1) if tm else ""
        game_id = dl.get("href", "").rstrip("/").split("/")[-1]

        games.append({
            "game_id": game_id,
            "home": home,
            "away": away,
            "score": score,
            "date": iso_date,       # ISO for comparison
            "time": gtime,
            "played": bool(score),
        })

    seen, unique = set(), []
    for g in games:
        if g["game_id"] and g["game_id"] not in seen:
            seen.add(g["game_id"])
            unique.append(g)
    return unique

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    # rounds[str(round_no)] = { "date": earliest_game_date, "games": [ {..., "grade": label} ] }
    rounds = {}

    for comp_path, label in COMPETITIONS:
        print(f"Scanning {label} ({comp_path})...")
        empty_streak = 0
        for rn in range(1, MAX_ROUNDS + 1):
            games = parse_round(comp_path, rn)
            if games:
                for g in games:
                    g["grade"] = label
                bucket = rounds.setdefault(str(rn), {"games": [], "date": ""})
                bucket["games"].extend(games)
                # round date = earliest game date in the round
                dates = [g["date"] for g in games if g["date"]]
                if dates:
                    d = min(dates)
                    bucket["date"] = d if not bucket["date"] else min(bucket["date"], d)
                empty_streak = 0
            else:
                empty_streak += 1
                if empty_streak >= MAX_EMPTY_ROUNDS and rounds:
                    break
            time.sleep(1)

    data = {
        "updated": datetime.now().isoformat(timespec="minutes"),
        "today": today,
        "rounds": rounds,
    }
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    total = sum(len(v["games"]) for v in rounds.values())
    print(f"Saved results.json — {total} games across {len(rounds)} rounds")

if __name__ == "__main__":
    main()
