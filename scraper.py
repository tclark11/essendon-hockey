import requests
from bs4 import BeautifulSoup
import json, time
from datetime import datetime

BASE = "https://www.hockeyvictoria.org.au"
CLUB = "Essendon Hockey"

# Fill in the grades Essendon Hockey plays in.
# Get the ID from the fixtures URL: /games/{ID}
COMPETITIONS = [
    # ("24681", "Men's Vic League 1"),
    # ("24682", "Women's Pennant A"),
]

def get_rounds(comp_id):
    r = requests.get(f"{BASE}/games/{comp_id}", timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    rounds = set()
    for a in soup.select("a[href*='/games/']"):
        parts = a.get("href", "").strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "games":
            rounds.add(a["href"])
    return sorted(rounds)

def parse_round(path):
    url = f"{BASE}{path}" if path.startswith("/") else f"{BASE}/{path}"
    r = requests.get(url, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    round_no = path.strip("/").split("/")[-1]
    games = []
    for card in soup.select("div.card, tr, div.fixture"):
        text = card.get_text(" ", strip=True)
        if CLUB.lower() not in text.lower():
            continue
        teams = [t.get_text(strip=True) for t in card.select("a[href*='/team/'], .team-name")]
        score = ""
        for s in card.select(".score, .result, strong"):
            st = s.get_text(strip=True)
            if any(c.isdigit() for c in st) and "-" in st:
                score = st
                break
        date = ""
        for d in card.select(".date, time, .fixture-date"):
            date = d.get_text(strip=True)
            if date:
                break
        games.append({
            "home": teams[0] if len(teams) > 0 else "",
            "away": teams[1] if len(teams) > 1 else "",
            "score": score,
            "date": date,
            "played": bool(score),
            "raw": text[:200],
        })
    return round_no, games

def main():
    data = {"updated": datetime.now().isoformat(timespec="minutes"), "grades": []}
    for comp_id, label in COMPETITIONS:
        print(f"Scanning {label}...")
        grade = {"label": label, "rounds": {}}
        try:
            for rnd in get_rounds(comp_id):
                round_no, games = parse_round(rnd)
                if games:
                    grade["rounds"].setdefault(round_no, []).extend(games)
                time.sleep(1)
        except Exception as e:
            print(f"  {label} failed: {e}")
        data["grades"].append(grade)

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved results.json — updated {data['updated']}")

if __name__ == "__main__":
    main()
