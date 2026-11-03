"""Repo file check: malformed files in a blog's repo, a live redirect sample, and fix counts in the ledger. Offline."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.audit.repo import RepoAudit, import_report, json_error, key_problem, parse_pairs  # noqa: E402
from core.audit.store import AuditStore  # noqa: E402
from core.discovery.fetch import FetchResult  # noqa: E402
from core.findings import FindingsStore  # noqa: E402
from core.items import counts, in_repo, repo_items, update  # noqa: E402
from core.tenant import Tenant  # noqa: E402

HOST = "blog.example.com"
GOOD = '{\n  "/old/": "https://blog.example.com/new/",\n  "/gone/": "https://blog.example.com/new/"\n}\n'
BAD = ('{\n  "/old/": "https://blog.example.com/new/",\n  "/gone/": "https://blog.example.com/new/",\n'
       '  "/self/": "https://blog.example.com/self/",\n  "/plain/": "http://blog.example.com/new/",\n'
       '  "blog.example.com/a/{{ token }}":"https://blog.example.com/a/"\n'
       '  "http://blog.example.com/b":"https://blog.example.com/b/"\n}\n')


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   check=True, capture_output=True)


def make_repo(tmp: Path, redirects: str = BAD) -> Path:
    repo = tmp / "repo"
    post = repo / "content/Blog/pdf/2026-a"
    post.mkdir(parents=True)
    git(repo.parent, "init", "-q", str(repo))
    (repo / "Redirects.json").write_text(GOOD, encoding="utf-8")
    (post / "index.md").write_text("---\ntitle: x\nurl: /pdf/a/\n---\nText\n", encoding="utf-8")
    (post / "index.th.md").write_text("---\ntitle: x\nurl: th/pdf/a/\n---\nText\n", encoding="utf-8")
    (post / "index.ja.md").write_text("```\n---\ntitle: x\nurl: /ja/pdf/a/\n---\nText\n```\n", encoding="utf-8")
    (post / "index.de.md").write_text('---\ntitle: "x\nurl: /de/pdf/a/\n---\nText\n', encoding="utf-8")
    (post / "index.fr.md").write_bytes("﻿---\ntitle: x\nurl: /fr/pdf/a/\n---\nText\n".encode())
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "first, valid")
    (repo / "Redirects.json").write_text(redirects, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add redirects")
    return repo


class FakeFetcher:
    def __init__(self, redirecting=()):
        self.redirecting, self.requests, self.asked = set(redirecting), 0, []

    def get(self, url, headers=None):
        self.requests += 1
        self.asked.append(url)
        if url in self.redirecting:
            return FetchResult(url, 200, final_url=url, redirects=[url], redirect_statuses=[301])
        return FetchResult(url, 404, final_url=url)


def make_tenant(repo):
    raw = {"property": "example.com", "hosts": [{"host": HOST, "local_path": str(repo), "fix_channel": "git-pr"}],
           "audit": {"default_lang": "en"}}
    return Tenant(property="example.com", gsc_properties=[], ga4_property_id=None, hosts=raw["hosts"],
                  excluded_host_patterns=[], raw=raw)


def run(repo, fetcher=None):
    return RepoAudit(make_tenant(repo), fetcher or FakeFetcher(), AuditStore(":memory:"), log=None).run()


def test_report_counts_every_repo_run_of_the_latest_day(tmp_path):
    from scripts.build_report import repo_summary
    assert repo_summary(tmp_path) is None
    for name, run_id in (("2026-11-01-run3", 3), ("2026-11-03-run7", 7), ("2026-11-03-run9", 9)):
        (tmp_path / f"repo-audit-{name}.json").write_text(f'{{"run_id": {run_id}, "summary": {{}}}}', encoding="utf-8")
    (tmp_path / "repo-audit-2026-11-03-run9-issues.csv").write_text("check\n", encoding="utf-8")
    s = repo_summary(tmp_path)
    assert (s["run_id"], s["run_ids"], s["date"]) == (9, [7, 9], "2026-11-03")


def test_key_problem():
    assert key_problem("/ok/%7B%7B%20t%20%7D%7D") is None and key_problem("/ok/") is None
    assert key_problem("/a/{{ t }}") == "unencoded template text"
    assert key_problem("blog.example.com/a/") == key_problem("http://blog.example.com/a") == "host or scheme in the key"
    assert key_problem("//a/") == "double slash"


def test_invalid_file_is_still_read_line_by_line():
    assert json_error(GOOD) is None and "line 7" in json_error(BAD)
    assert [p[1] for p in parse_pairs(BAD)][-2:] == ["blog.example.com/a/{{ token }}", "http://blog.example.com/b"]


def test_finds_every_kind_and_names_the_commit(tmp_path):
    report = run(make_repo(tmp_path))
    checks = {f["check"]: f for f in report["findings"]}
    assert set(checks) == {"redirect_file_invalid", "redirect_not_working", "redirect_key_malformed",
                           "redirect_self_loop", "redirect_target_bad", "post_front_matter_broken", "post_url_relative"}
    invalid = checks["redirect_file_invalid"]
    assert invalid["type"] == "broken" and "add redirects" in invalid["evidence"]["observed"]
    assert report["summary"][HOST]["broke_it"].endswith("add redirects")
    assert checks["redirect_key_malformed"]["affected_pages"] == 2
    assert checks["post_url_relative"]["affected_pages"] == 1
    # a code fence and invalid YAML are broken; a byte-order mark is not
    broken = [i["file"] for i in report["hosts"][HOST]["issues"] if i["check"] == "post_front_matter_broken"]
    assert sorted(Path(f).name for f in broken) == ["index.de.md", "index.ja.md"]
    assert "author" not in str(report["findings"])


def test_live_sample_only_uses_wellformed_keys_and_a_redirect_passes(tmp_path):
    fetcher = FakeFetcher({f"https://{HOST}/old/"})
    live = run(make_repo(tmp_path), fetcher)["hosts"][HOST]["redirects"]["live"]
    assert live["sampled"] == live["eligible"] == 4 and live["redirected"] == 1 and live["not_working"] == 3
    assert not [u for u in fetcher.asked if "{{" in u or "blog.example.com/blog.example.com" in u]


def test_valid_repo_with_working_redirects_has_no_redirect_findings(tmp_path):
    repo = make_repo(tmp_path, redirects=GOOD + "\n")
    fetcher = FakeFetcher({f"https://{HOST}/old/", f"https://{HOST}/gone/"})
    assert not [f for f in run(repo, fetcher)["findings"] if f["check"].startswith("redirect")]


def test_fix_counts_in_ledger_and_findings_resolve(tmp_path):
    repo = make_repo(tmp_path)
    first = run(repo)
    store = FindingsStore(":memory:")
    import_report(store, first)
    ledger = update({}, "repo-audit-run1", "2026-11-03", repo_items(first), in_repo({HOST: str(repo)}), source="repo-audit")
    before = counts(ledger, HOST)
    assert before["by_check"]["redirect_file_invalid"]["open"] == 1 and before["fixed"] == 0

    (repo / "Redirects.json").write_text(GOOD, encoding="utf-8")  # the revert
    second = run(repo, FakeFetcher({f"https://{HOST}/old/", f"https://{HOST}/gone/"}))
    second["run_id"] = first["run_id"] + 1
    ledger = update(ledger, "repo-audit-run2", "2026-11-04", repo_items(second), in_repo({HOST: str(repo)}),
                    source="repo-audit")
    after = counts(ledger, HOST)["by_check"]
    assert after["redirect_file_invalid"] == {**after["redirect_file_invalid"], "fixed": 1, "open": 0, "fixed_pct": 100}
    assert after["redirect_key_malformed"]["fixed"] == 2
    assert after["post_url_relative"]["open"] == 1  # not touched by the revert
    changes = import_report(store, second)
    assert changes["resolved"]
