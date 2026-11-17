#!/usr/bin/env python3
"""Monitor NEW Avengers: Doomsday showtimes at AAA Cinemas and Prasads.

Public theatre pages only. The program does not bypass anti-bot measures,
book tickets, or claim that Dolby Atmos implies certified Dolby Cinema.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

import requests
from bs4 import BeautifulSoup

FILM = "Avengers: Doomsday"
SHOW_DATE = "2026-12-17"
STATE_PATH = Path("state/seen_shows.json")
THEATRES = {
    "AAA Cinemas: Ameerpet": "https://in.bookmyshow.com/cinemas/hyderabad/aaa-cinemas-ameerpet/buytickets/ACAS/20261217",
    "Prasads Multiplex: Hyderabad": "https://in.bookmyshow.com/cinemas/hyderabad/prasads-multiplex-hyderabad/buytickets/PRHN/20261217",
}
MOVIE_TITLE = re.compile(r"^Avengers\s*(?::|\s)\s*Doomsday\s*(?:\([^)]*\))?$", re.I)
# All certificate formats used by the platform, including "UA 7+".
CERT = r"(?:U|A|UA\s*\d*\s*\+?)"
RATED_TITLE = re.compile(r"^.{2,140}\s*\(" + CERT + r"\)\s*$", re.I)
ONLY_CERT = re.compile(r"^\(" + CERT + r"\)$", re.I)
TIME = re.compile(r"^(?:0?[1-9]|1[0-2]):[0-5]\d\s*(?:AM|PM)$", re.I)
FORMAT = re.compile(r"^(?:English|Telugu|Hindi|Tamil|Malayalam|Kannada|Marathi)\s*[,\-]", re.I)
END_SECTION = re.compile(r"^(?:Movies Now Showing|Top Cinemas|Upcoming Movies|List your Show|Movie Tickets|You might also like|About the cinema)", re.I)
BLOCKED = re.compile(r"access denied|verify you are human|captcha|unusual traffic|request blocked", re.I)
DATE_VISIBLE = re.compile(r"(?:thu\s+17\s+dec|17\s+dec(?:ember)?|dec(?:ember)?\s+17|17\s*[/\-]\s*12\s*[/\-]\s*2026)", re.I)


def visible_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "template"]):
        element.decompose()
    root = soup.body or soup
    return [re.sub(r"\s+", " ", x).strip() for x in root.get_text("\n", strip=True).splitlines() if x.strip()]


def is_heading(lines, i):
    line = lines[i]
    if RATED_TITLE.fullmatch(line):
        return True
    # Some pages place the film title and its certificate on separate lines.
    return i + 1 < len(lines) and ONLY_CERT.fullmatch(lines[i + 1]) is not None and len(line) > 2


def parse_shows(html, theatre):
    """Return a list of (theatre, date, language/format, time, screen) tuples.

    Only read showtimes in the Avengers film section; other movies' screen
    labels and times are never attached to the target film.
    """
    lines = visible_lines(html)
    joined = " ".join(lines)
    if not lines or len(joined) < 30:
        raise RuntimeError("Empty / incomplete cinema page")
    if BLOCKED.search(joined):
        raise RuntimeError("Access challenge; cannot verify showtimes")
    if not all(word.lower() in joined.lower() for word in theatre.split(":")[0].split()):
        raise RuntimeError("Theatre identity missing; possible redirect or incorrect page")

    watching = False
    format_name = "Unspecified format"
    found = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if END_SECTION.match(line):
            watching = False
        if is_heading(lines, i):
            watching = bool(MOVIE_TITLE.fullmatch(line))
            format_name = "Unspecified format"
            if i + 1 < len(lines) and ONLY_CERT.fullmatch(lines[i + 1]):
                i += 1
            i += 1
            continue
        # Works if the film has not yet received a certificate.
        if MOVIE_TITLE.fullmatch(line):
            watching = True
            format_name = "Unspecified format"
            i += 1
            continue
        if watching and FORMAT.match(line):
            format_name = line
        if watching and TIME.fullmatch(line):
            # A label can be on the following line (or absent). Stop at the
            # next showtime, language, or movie heading to avoid bleed-over.
            label = "Screen not specified"
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j]
                if TIME.fullmatch(next_line) or is_heading(lines, j) or FORMAT.match(next_line) or END_SECTION.match(next_line):
                    break
                if next_line.lower() in {"available", "fast filling", "non-cancellable", "mticket", "subtitles language", "subtitle language"}:
                    continue
                if re.search(r"laser|atmos|dolby|led|pcx|screen|barco|hdr|imax|4k|7\.1|dts|lux", next_line, re.I):
                    label = next_line
                    break
            found.append((theatre, SHOW_DATE, format_name, line.upper(), label.upper()))
        i += 1

    # Do not label an Avengers listing as 17 Dec if BookMyShow redirected to
    # another date or removed that date from the accessible page.
    if found and not DATE_VISIBLE.search(joined):
        raise RuntimeError("Avengers shows found, but 17 Dec isn't visible; cannot verify the requested date")
    return sorted(set(found))


def load_state(path=STATE_PATH):
    if not path.exists():
        return {"date": SHOW_DATE, "theatres": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("date") != SHOW_DATE:
        raise RuntimeError("Stored show date differs from configuration; reset state explicitly")
    return data


def save_state(state, path=STATE_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def new_shows(previous, current):
    """No alert on first successful check; later alert on brand-new entries."""
    new = sorted(set(current) - set(previous))
    return new


def fetch(url):
    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; PublicShowtimeChecker/1.0)",
        "Accept-Language": "en-IN,en;q=0.9",
    }, timeout=25)
    response.raise_for_status()
    if len(response.content) < 800:
        raise RuntimeError("Page is too small to contain trustworthy showtime details")
    return response.text


def notify(topic, shows, test=False):
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", topic):
        raise RuntimeError("NTFY_TOPIC must contain 16–128 letters/numbers/_/-; set it as a GitHub secret")
    if test:
        title = "TEST: Avengers ticket monitor"
        body = "Phone alert test succeeded. No BookMyShow availability was checked."
        click = list(THEATRES.values())[0]
    else:
        title = f"{len(shows)} NEW Avengers show(s) — Hyderabad"
        parts = []
        for theatre, day, format_name, time, screen in shows[:12]:
            parts.append(f"{theatre}: {time} | {format_name} | {screen}")
        body = "Avengers: Doomsday — 17 Dec 2026\n" + "\n".join(parts)
        if len(shows) > 12:
            body += f"\n...and {len(shows) - 12} more."
        body += "\nOpen BookMyShow and verify before booking."
        click = THEATRES[shows[0][0]]
    response = requests.post("https://ntfy.sh/" + topic,
        data=body.encode("utf-8"),
        headers={"Title": title, "Priority": "5", "Tags": "ticket", "Click": click},
        timeout=15)
    response.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description="Watch new Avengers showtimes at AAA / Prasads on 17 Dec 2026")
    parser.add_argument("--test-notification", action="store_true", help="Send a test push only")
    parser.add_argument("--aaa-html", help="Use offline AAA fixture")
    parser.add_argument("--prasads-html", help="Use offline Prasads fixture")
    args = parser.parse_args()
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if args.test_notification:
        notify(topic, [], test=True)
        print("Sent test notification")
        return

    state = load_state()
    failures = []
    changes = []
    successful = 0
    fixtures = {"AAA Cinemas: Ameerpet": args.aaa_html, "Prasads Multiplex: Hyderabad": args.prasads_html}
    updated = False

    for theatre, url in THEATRES.items():
        try:
            html = Path(fixtures[theatre]).read_text(encoding="utf-8") if fixtures[theatre] else fetch(url)
            shows = parse_shows(html, theatre)
        except (requests.RequestException, RuntimeError, OSError) as exc:
            failures.append(f"{theatre}: {exc}")
            continue
        successful += 1
        serialized = [list(s) for s in shows]
        entry = state["theatres"].get(theatre)
        if entry is None:
            # Do not alert on shows already present when monitoring begins.
            state["theatres"][theatre] = {"seen": serialized}
            updated = True
            print(f"{theatre}: baseline recorded ({len(shows)} existing shows); no phone alert")
            continue
        previous = [tuple(x) for x in entry.get("seen", [])]
        added = new_shows(previous, shows)
        changes.extend(added)
        print(f"{theatre}: {len(shows)} now listed, {len(added)} new")

    if updated:
        save_state(state)

    if changes:
        # Persist only after a successful phone notification, so failed alert
        # delivery is eligible for retry on the next run.
        notify(topic, changes)
        for theatre in THEATRES:
            entry = state["theatres"].get(theatre)
            if entry is not None:
                old = [tuple(x) for x in entry.get("seen", [])]
                additions = [x for x in changes if x[0] == theatre]
                entry["seen"] = [list(x) for x in sorted(set(old) | set(additions))]
        save_state(state)
        print(f"ALERT SENT: {len(changes)} new Avengers show(s)")

    for err in failures:
        print("WARNING:", err, file=sys.stderr)
    if successful == 0:
        raise RuntimeError("Neither theatre could be checked. Review HTTP access, date and page layout")
    if failures:
        print("Some checks failed; monitor continued for accessible theatres")


if __name__ == "__main__":
    main()
