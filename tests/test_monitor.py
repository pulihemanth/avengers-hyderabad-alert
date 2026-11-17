import unittest
from monitor import parse_shows, new_shows

AAA = "AAA Cinemas: Ameerpet"
PRASADS = "Prasads Multiplex: Hyderabad"

def page(theatre, listing, date="Thu 17 Dec"):
    return f'<html><body><h1>{theatre}</h1><nav>{date}</nav><h2>Movie Shows</h2>{listing}</body></html>'


class ParseTests(unittest.TestCase):
    def test_only_avengers_shows_not_other_films(self):
        html = page(AAA, '<div>Avengers: Doomsday (UA16+)<p>English, 3D</p><p>10:15 AM</p><p>LASER 4K ATMOS</p></div>'
                         '<div>Different Movie (UA16+)<p>01:15 PM</p><p>LED SCREEN DOLBY ATMOS</p></div>')
        shows = parse_shows(html, AAA)
        self.assertEqual(len(shows), 1)
        self.assertEqual(shows[0][-1], "LASER 4K ATMOS")

    def test_multiple_shows_languages_and_labels(self):
        html = page(AAA, '<div>Avengers: Doomsday (UA16+)</div><p>English, 3D</p><p>10:15 AM</p><p>LASER 4K ATMOS</p>'
                         '<p>07:30 PM</p><p>LED SCREEN DOLBY ATMOS</p><p>Hindi, 2D</p><p>11:30 AM</p><p>LASER DOLBY ATMOS</p>')
        shows = parse_shows(html, AAA)
        self.assertEqual(len(shows), 3)
        self.assertEqual({s[-1] for s in shows}, {"LASER 4K ATMOS", "LED SCREEN DOLBY ATMOS", "LASER DOLBY ATMOS"})

    def test_no_avengers(self):
        self.assertEqual(parse_shows(page(AAA, '<p>Another Movie (U)</p><p>10:10 AM</p>'), AAA), [])

    def test_different_theatre(self):
        shows = parse_shows(page(PRASADS, '<p>Avengers: Doomsday (UA16+)</p><p>English, 3D</p><p>11:00 AM</p><p>PCX Screen</p>'), PRASADS)
        self.assertEqual(len(shows), 1)
        self.assertEqual(shows[0][-1], 'PCX SCREEN')
        self.assertEqual(shows[0][0], PRASADS)

    def test_same_time_new_screen_counts(self):
        old = [(AAA, "2026-12-17", "English, 3D", "10:15 AM", "LASER 4K ATMOS")]
        now = old + [(AAA, "2026-12-17", "English, 3D", "10:15 AM", "LED SCREEN DOLBY ATMOS")]
        self.assertEqual(new_shows(old, now), [now[1]])

    def test_not_associate_other_film_screen_label(self):
        html = page(AAA, '<p>Avengers: Doomsday (UA16+)</p><p>10:15 AM</p><p>LASER 4K ATMOS</p>'
                         '<p>Other Film (UA16+)</p><p>11:15 AM</p><p>LED SCREEN DOLBY ATMOS</p>')
        self.assertEqual(len(parse_shows(html, AAA)), 1)

    def test_no_date_verification(self):
        html = page(AAA, '<p>Avengers: Doomsday (UA16+)</p><p>10:15 AM</p><p>LASER 4K ATMOS</p>', "Tue 17 Nov")
        with self.assertRaisesRegex(RuntimeError, "17 Dec"):
            parse_shows(html, AAA)

    def test_blocked_site(self):
        html = page(AAA, 'Access denied - verify you are human')
        with self.assertRaisesRegex(RuntimeError, "challenge"):
            parse_shows(html, AAA)

    def test_no_label_still_count_show(self):
        html = page(PRASADS, '<p>Avengers: Doomsday (UA16+)</p><p>English, 2D</p><p>11:00 AM</p>')
        self.assertEqual(parse_shows(html, PRASADS)[0][-1], "SCREEN NOT SPECIFIED")


if __name__ == '__main__':
    unittest.main()
