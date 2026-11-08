import unittest
from datetime import date, datetime, timedelta, timezone

from githoroscope import analysis as an
from githoroscope.gitlog import Commit, FileChange, normalise_path, parse_log
from githoroscope.horoscope import weekly_change_probability, zodiac

TZ = timezone(timedelta(hours=5))


def commit(day, hour, files, msg="Add feature", author="Ann"):
    when = datetime(2026, 3, 2, tzinfo=TZ) + timedelta(days=day, hours=hour)  # 2026-03-02 is a Monday
    return Commit(f"sha{day}{hour}{msg}", author, f"{author}@x", when, msg, [FileChange(f, 5, 1) for f in files])


class ParseTests(unittest.TestCase):
    def test_parse_log_with_numstat_binary_and_renames(self):
        rs, us = "\x1e", "\x1f"
        text = (
            f"{rs}abc{us}Ann{us}ann@x{us}2026-03-02T23:15:00+05:00{us}Add login\n"
            "10\t2\tsrc/login.py\n-\t-\tlogo.png\n3\t0\tsrc/{old => new}/util.py\n"
            f"{rs}def{us}Bob{us}bob@x{us}2026-03-01T09:00:00+05:00{us}Initial commit\n1\t0\tREADME.md\n"
        )
        cs = parse_log(text)
        self.assertEqual([c.sha for c in cs], ["def", "abc"])  # sorted by time
        login = cs[1]
        self.assertEqual(login.when.hour, 23)  # the author's local hour, not UTC
        self.assertEqual([f.path for f in login.files], ["src/login.py", "logo.png", "src/new/util.py"])
        self.assertEqual(login.files[1].churn, 0)
        self.assertEqual(login.churn, 15)

    def test_normalise_path(self):
        self.assertEqual(normalise_path("a/{b => c}/d.py"), "a/c/d.py")
        self.assertEqual(normalise_path("src/{ => sub}/x.py"), "src/sub/x.py")
        self.assertEqual(normalise_path("old.py => new.py"), "new.py")
        self.assertEqual(normalise_path("plain.py"), "plain.py")


class AnalysisTests(unittest.TestCase):
    def test_heatmap_and_chronotype(self):
        cs = [commit(0, 23, ["a"]), commit(1, 2, ["a"]), commit(2, 1, ["a"]), commit(3, 14, ["a"])]
        grid = an.heatmap(cs)
        self.assertEqual(grid[0][23], 1)
        self.assertEqual(sum(map(sum, grid)), 4)
        kind, night, _ = an.chronotype(cs)
        self.assertTrue(kind.startswith("Night Owl"))
        self.assertEqual(night, 0.75)

    def test_hotspots_rank_frequent_and_big_files(self):
        cs = [commit(i, 10, ["big.py"]) for i in range(5)] + [commit(i, 10, ["small.py"]) for i in range(5)] + [commit(1, 11, ["gone.py"])]
        hs = an.hotspots(cs, {"big.py": 900, "small.py": 3})
        self.assertEqual([h.path for h in hs], ["big.py", "small.py"])  # deleted files are ignored

    def test_knowledge_islands_and_bus_factor(self):
        cs = [commit(i, 10, ["core.py"], author="Ann") for i in range(4)]
        cs += [commit(i, 11, ["ui.py"], author="Ann") for i in range(3)]
        cs += [commit(i, 12, ["docs.md"], author="Bob") for i in range(2)]
        islands, bus = an.knowledge(cs, {"core.py": 10, "ui.py": 10, "docs.md": 10})
        self.assertEqual({i.path for i in islands}, {"core.py", "ui.py", "docs.md"})
        self.assertEqual(bus, 1)  # Ann alone is the main author of 2 of 3 files

    def test_coupling(self):
        cs = [commit(i, 10, ["routes.py", "schemas.py"]) for i in range(4)] + [commit(9, 10, ["routes.py"])]
        (a, b, n, degree), = an.coupling(cs, min_shared=3)
        self.assertEqual((a, b, n), ("routes.py", "schemas.py", 4))
        self.assertEqual(degree, 1.0)

    def test_regret_penalty_for_night_commits(self):
        cs = []
        for d in range(4):
            cs.append(commit(d * 4, 2, [f"n{d}.py"], "Add thing"))  # night commit…
            cs.append(commit(d * 4, 12, [f"n{d}.py"], "Fix thing"))  # …fixed the same day
            cs.append(commit(d * 4 + 1, 14, [f"d{d}.py"], "Add other"))  # day commit, never fixed
        cs.append(commit(30, 15, ["x.py"], "Add x"))
        cs.append(commit(30, 16, ["x.py"], "oops typo"))
        cs.sort(key=lambda c: c.when)
        reg, penalty = an.regret(cs)
        self.assertEqual(reg["night"], (4, 4))
        self.assertIsNotNone(penalty)
        self.assertGreater(penalty, 2)

    def test_messages(self):
        cs = [commit(i, 10, ["a"], m) for i, m in enumerate(["wip", "final2", "Add OAuth login flow", "asdf", "Fix crash on empty cart", "!!!!"])]
        avg, panic, fixes, worst = an.messages(cs)
        self.assertEqual(panic, round(4 / 6, 3))
        self.assertIn("wip", worst)
        self.assertNotIn("Fix crash on empty cart", worst)
        self.assertEqual(fixes, round(1 / 6, 3))

    def test_streaks(self):
        cs = [commit(d, 10, ["a"]) for d in (0, 1, 2, 3, 10, 11)]
        self.assertEqual(an.streaks(cs), (4, 6))

    def test_empty_repo(self):
        with self.assertRaises(ValueError):
            an.analyze([], {})


class HoroscopeTests(unittest.TestCase):
    def test_zodiac_boundaries(self):
        self.assertEqual(zodiac(date(2026, 1, 5))[0], "Capricorn")
        self.assertEqual(zodiac(date(2026, 12, 25))[0], "Capricorn")
        self.assertEqual(zodiac(date(2026, 1, 20))[0], "Aquarius")
        self.assertEqual(zodiac(date(2026, 3, 21))[0], "Aries")
        self.assertEqual(zodiac(date(2026, 11, 8))[0], "Scorpio")
        self.assertEqual(zodiac(date(2026, 12, 21))[0], "Sagittarius")

    def test_weekly_probability_is_poisson(self):
        self.assertAlmostEqual(weekly_change_probability(1, "2026-01-01", "2026-01-08"), 1 - 2.718281828 ** -1, places=4)
        self.assertLess(weekly_change_probability(1, "2026-01-01", "2026-12-31"), 0.05)


if __name__ == "__main__":
    unittest.main()
