# Avengers: Doomsday — Hyderabad New Show Alert

This customized monitor checks **17 December 2026** show listings on BookMyShow for:

- **AAA Cinemas: Ameerpet** (`ACAS`): all new Avengers showtimes, including LASER 4K ATMOS, LED SCREEN DOLBY ATMOS or other screen labels.
- **Prasads Multiplex: Hyderabad** (`PRHN`): all new Avengers showtimes, including PCX Screen, BARCO 4K LASER, etc.

**How alerts work**: On the **first successful check** of each theatre, the monitor silently records the shows already there (baseline). On a later check, it sends **one push notification for newly added showtimes / new screen-format combinations**, with theatre, time, screen label and a booking link. It remembers everything previously seen to avoid repeated alerts. Removing and re-adding an identical listing will not trigger a second notification.

A `LASER 4K ATMOS` label is **not evidence of certified Dolby Cinema**. The monitor uses whatever screen label BookMyShow actually displays.

## Phone setup (Samsung Galaxy S24 Ultra)

1. Install [ntfy](https://play.google.com/store/apps/details?id=io.heckel.ntfy) from Google Play.
2. Open ntfy → press **+** → subscribe to a long, random topic on `ntfy.sh` that only you know. Keep the topic private. You can reuse your earlier topic if already subscribed.
3. Samsung Settings → Apps → ntfy → Notifications → Allow notifications, sound and pop-up. Also set App → Battery → Unrestricted and exclude ntfy from Sleeping apps if notifications are delayed.

## Host using GitHub Actions

1. Create a GitHub repository (public to use GitHub-hosted runners without private-repo minutes constraints; **do not put the ntfy topic into code**).
2. Upload the **contents** of this zip, preserving the hidden `.github/workflows/check-aaa-dolby.yml` folder. Note: GitHub's web upload interface may not preserve the workflow path if you only drag files; verify the exact `.github/workflows/` location appears in your repository.
3. Repository → **Settings → Secrets and variables → Actions → New repository secret**. Add `NTFY_TOPIC` = your ntfy topic.
4. Repository → **Actions → Avengers Hyderabad New Shows → Run workflow**. Select the **test notification** checkbox; run. A test message should arrive in the phone ntfy app.
5. Run the workflow again with **test notification unchecked**. In the run logs, verify both theatres were checked. If one succeeds, the monitor still covers that theatre. If either is blocked by BookMyShow, **monitoring that theatre is not reliable**.
6. The first successful check silently establishes a **baseline**. Later newly added shows trigger a phone notification. Open the notification to visit the theatre's booking page.

The GitHub workflow is configured with cron `*/5 * * * *`. GitHub Actions scheduling is **best-effort**, can be delayed or occasionally skipped, and is **not an exact five-minute guarantee**. Scheduled workflows on public repositories may disable after extended inactivity. If you need high reliability, deploy the same Python file on a trusted paid host with a true 5-minute scheduler instead.

## BookMyShow links

- [AAA Cinemas: Ameerpet — 17 Dec](https://in.bookmyshow.com/cinemas/hyderabad/aaa-cinemas-ameerpet/buytickets/ACAS/20261217)
- [Prasads Multiplex: Hyderabad — 17 Dec](https://in.bookmyshow.com/cinemas/hyderabad/prasads-multiplex-hyderabad/buytickets/PRHN/20261217)

## Limitations

- **Not deployed yet**. Downloading this zip does not activate monitoring.
- No BookMyShow account, official API, or booking permission is used. BookMyShow may block automated requests or not expose dates/shows in HTML. If so, the program will log a warning; it **cannot guarantee detection** and does not bypass website protections.
- The website may expose the requested date in the URL while redirecting to a different week. When shows are found without an explicit visible reference to **17 December**, the program refuses to alert.
- A movie listing is not confirmation of seat availability. Book tickets manually and verify screen format at checkout.
- The change detector stores a baseline on the first successful run; if you start monitoring after a show was added, it won't alert you about that old show.
- New times at either theatre are in scope. It does **not** track every other Hyderabad theatre or every other movie.

## Test locally

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python monitor.py --test-notification      # requires NTFY_TOPIC env variable
python monitor.py                          # checks websites; requires connectivity
```
