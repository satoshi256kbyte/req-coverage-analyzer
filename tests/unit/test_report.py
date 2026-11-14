from req_coverage_runner.coverage import Coverage, Match
from req_coverage_runner.csv_io import Row
from req_coverage_runner.report import RunMeta, render_markdown

META = RunMeta("r1", "m", "t0", "t1")


def test_利用者の文は_Markdownの記号を文字として出す():
    requirements = [Row("R1", "a|b <img src=x> ![x](http://example.com) `c` d\n改行")]
    tests = [Row("T1", "t")]
    coverage = [Coverage("R1", True, [Match("T1", 0.9, 0.9)])]

    text = render_markdown(META, requirements, tests, coverage)

    assert "a\\|b \\<img src=x\\> \\!\\[x\\](http://example.com) \\`c\\` d 改行" in text
    assert "<img" not in text.replace("\\<img", "")
