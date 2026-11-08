import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from githoroscope.__main__ import main
from githoroscope.analysis import analyze
from githoroscope.demo import create_demo_repo
from githoroscope.gitlog import current_files, read_commits
from githoroscope.horoscope import readings
from githoroscope.report import render


class DemoRepoTests(unittest.TestCase):
    """The demo repo has planted patterns; the analysis must find every one of them."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = create_demo_repo(Path(cls.tmp.name) / "shop-backend")
        cls.a = analyze(read_commits(cls.repo), current_files(cls.repo))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_finds_the_planted_hotspot(self):
        self.assertEqual(self.a.hotspots[0].path, "src/payments/checkout.py")

    def test_finds_the_planted_soulmates(self):
        x, y, _, degree = self.a.coupling[0]
        self.assertEqual({x, y}, {"src/api/routes.py", "src/api/schemas.py"})
        self.assertGreater(degree, 0.7)

    def test_finds_the_planted_knowledge_island(self):
        island = next(i for i in self.a.islands if i.path == "src/legacy/billing_v1.py")
        self.assertEqual(island.owner, "Dilshod Rakhimov")

    def test_finds_the_planted_night_regret(self):
        self.assertIsNotNone(self.a.night_penalty)
        self.assertGreater(self.a.night_penalty, 2)

    def test_every_reading_has_evidence(self):
        rs = readings(self.a, "shop-backend")
        self.assertGreaterEqual(len(rs), 8)
        for r in rs:
            self.assertTrue(r.text and r.title)

    def test_html_report(self):
        page = render(self.a, "shop-backend")
        for s in ("Hotspots", "Regret by time of day", "Soulmate files", "Knowledge islands", "checkout.py"):
            self.assertIn(s, page)

    def test_report_escapes_hostile_names(self):
        self.a.authors.insert(0, ("<img src=x onerror=alert(1)>", 1))
        try:
            self.assertNotIn("<img src=x", render(self.a, "<b>repo</b>"))
        finally:
            self.a.authors.pop(0)

    def test_filters(self):
        only = read_commits(self.repo, author="Sevara")
        self.assertTrue(only)
        self.assertTrue(all(c.author == "Sevara Aliyeva" for c in only))


class CliTests(unittest.TestCase):
    def test_demo_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main(["--demo", "--json"]), 0)
        data = json.loads(buf.getvalue())
        self.assertGreater(data["n_commits"], 100)

    def test_html_output(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "h.html"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--demo", "--no-open", "--html", str(out)]), 0)
            self.assertIn("Git Horoscope", out.read_text(encoding="utf-8"))

    def test_not_a_repo(self):
        with tempfile.TemporaryDirectory() as d, redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main([d, "--no-open"]), 1)
        self.assertIn("stars are unclear", err.getvalue())


if __name__ == "__main__":
    unittest.main()
