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
DESC = ("seoTitle: A post title that is long enough\n"
        "description: A description that is long enough for the search result.\n")
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
    (post / "index.md").write_text("---\ntitle: x\n" + DESC + "url: /pdf/a/\n---\nText\n", encoding="utf-8")
    (post / "index.th.md").write_text("---\ntitle: x\n" + DESC + "url: th/pdf/a/\n---\nText\n", encoding="utf-8")
    (post / "index.ja.md").write_text("```\n---\ntitle: x\n" + DESC + "url: /ja/pdf/a/\n---\nText\n```\n",
                                      encoding="utf-8")
    (post / "index.de.md").write_text('---\ntitle: "x\nurl: /de/pdf/a/\n---\nText\n', encoding="utf-8")
    (post / "index.fr.md").write_bytes(("﻿---\ntitle: x\n" + DESC + "url: /fr/pdf/a/\n---\nText\n").encode())
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
    # junk entries (SK, 2026-11-11): no redirect for URLs that are not real blog URLs
    assert key_problem("/ok/") is None and key_problem("/2021/09/10/convert-html-to-pdf-using-java") is None
    assert key_problem("/a/{{ revealButtonHref }}").startswith("gist placeholder")
    assert key_problem("/a/%7B%7B%20revealButtonHref%20%7D%7D").startswith("gist placeholder")  # encoded too
    assert key_problem("blog.example.com/a/") == key_problem("http://blog.example.com/a") == "host or scheme in the key"
    assert key_problem("/a/%23:~:text=x").startswith("fragment") and key_problem("/a/#b").startswith("fragment")
    assert key_problem("//a/") == key_problem("/a//b/") == "double slash"  # it redirects, but is junk
    assert key_problem("/2017/07/02/2017年7月aspose/") == "non-English slug"
    assert key_problem("/fr/total/cr%C3%A9ez-votre-application/") == "non-English slug"  # encoded too


def test_invalid_file_is_still_read_line_by_line():
    assert json_error(GOOD) is None and "line 7" in json_error(BAD)
    assert [p[1] for p in parse_pairs(BAD)][-2:] == ["blog.example.com/a/{{ token }}", "http://blog.example.com/b"]


def test_finds_every_kind_and_names_the_commit(tmp_path):
    report = run(make_repo(tmp_path))
    checks = {f["check"]: f for f in report["findings"]}
    checks.pop("post_text_untranslated")  # the fixture's translations copy the English seoTitle: right to flag
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


def test_translated_url_mismatch(tmp_path):
    repo = make_repo(tmp_path)
    post = repo / "content/Blog/pdf/2026-01-02-b"
    post.mkdir(parents=True)
    (post / "index.md").write_text("---\ntitle: b\nurl: /pdf/b/\n---\n", encoding="utf-8")
    for lang, url in {"de": "/de/pdf/b/", "fr": "/fr/pdf/créez-b/", "zh-hant": "/zh-tw/pdf/b/", "fa": "/fr/pdf/b/",
                      "id": "/pdf/b/", "ko": "ko/pdf/b/"}.items():
        (post / f"index.{lang}.md").write_text(f"---\ntitle: b\nurl: {url}\n---\n", encoding="utf-8")
    audit = RepoAudit(make_tenant(repo), FakeFetcher(), AuditStore(":memory:"), sample=0, log=None)
    issues = [i for i in audit.check_posts(HOST)[0] if i["check"] == "translated_url_mismatch"]
    got = {i["file"].rsplit(".", 2)[-2]: (i["note"], i["fix"]) for i in issues}
    assert got == {"fr": ("own slug (translated or changed)", "/fr/pdf/b/"),
                   "zh-hant": ("language prefix zh-tw on a zh-hant post", "/zh-hant/pdf/b/"),
                   "fa": ("language prefix fr on a fa post", "/fa/pdf/b/"),
                   "id": ("same URL as the English post (no language prefix)", "/id/pdf/b/")}


def test_site_checks_found_by_hand_on_a_small_blog(tmp_path):
    """The blog.conholdate.cloud session (11 Nov) found these by hand; the repo check must find them now."""
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", str(repo))
    (repo / "config.yml").write_text(
        "params:\n  mainSections: [Blog]\nlanguages:\n  en: {languageName: English}\n"
        "  ja: {languageName: 日本}\n  ar: {languageName: عربي}\n"
        "  ko: {languageName: 한국어, languageDirection: ltr}\n",
        encoding="utf-8")
    ok = "seoTitle: A post title that is long enough\ndescription: " + "d" * 60 + "\n"
    a = repo / "content/Blog/total/a"
    a.mkdir(parents=True)
    (repo / "content/Blog/_index.md").write_text("---\ntitle: Blog\n---\n", encoding="utf-8")
    (a / "index.md").write_text("---\n" + ok + "url: /total/a/\ncategories: [Family]\n---\n", encoding="utf-8")
    (a / "index.ja.md").write_text("---\n" + ok + "url: /ja/total/a/\n---\n", encoding="utf-8")
    (a / "index.ar.md").write_text("---\nseoTitle: عنوان طويل بما يكفي للبحث هنا\ndescription: " + "d" * 60
                                   + "\nurl: /ar/total/a/\n---\n", encoding="utf-8")
    b = repo / "content/Other/b"
    b.mkdir(parents=True)
    (b / "index.md").write_text("---\nseoTitle: " + "t" * 80 + "\ndescription: short\nurl: /b/\n---\n",
                                encoding="utf-8")
    cat = repo / "content/categories/old-family"
    cat.mkdir(parents=True)
    (cat / "_index.md").write_text("---\ntitle: Old Family\n---\n", encoding="utf-8")
    git(repo, "add", "-A")
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm",
                    "first"], check=True, capture_output=True,
                   env={"GIT_COMMITTER_DATE": "2026-01-01T00:00:00", "PATH": "/usr/bin:/bin:/usr/local/bin"})
    (a / "index.md").write_text("---\nseoTitle: A new post title that is long enough\ndescription: " + "e" * 60 +
                                "\nurl: /total/a/\ncategories: [Family]\n---\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qam",
                    "rewrite English title"], check=True, capture_output=True,
                   env={"GIT_COMMITTER_DATE": "2026-07-01T00:00:00", "PATH": "/usr/bin:/bin:/usr/local/bin"})

    class Slash(FakeFetcher):
        def get(self, url, headers=None):
            self.requests += 1
            return FetchResult(url, 200, final_url=url + "/", redirects=[url], redirect_statuses=[302])

    report = run(repo, Slash())
    by = {}
    for i in report["hosts"][HOST]["issues"]:
        by.setdefault(i["check"], []).append(i)
    assert {i["file"] for i in by["post_title_length"]} == {"content/Other/b/index.md"}
    assert {i["file"] for i in by["post_description_length"]} == {"content/Other/b/index.md"}
    assert [i["file"] for i in by["post_outside_main_sections"]] == ["content/Other/b/index.md"]
    assert [i["file"] for i in by["translation_stale"]] == ["content/Blog/total/a/index.ar.md",
                                                            "content/Blog/total/a/index.ja.md"]
    # ja copies the old English seoTitle (differs from today's); ar has its own title but the same description,
    # which is no Latin words (d's only) and so not counted
    assert [i["file"] for i in by.get("post_text_untranslated", [])] == []
    assert [i["file"] for i in by["section_index_untranslated"]] == ["content/Blog/_index.ar.md",
                                                                     "content/Blog/_index.ja.md"]
    assert [i["link"] for i in by["language_name_wrong"]] == ["ja"]  # عربي is accepted
    assert [i["link"] for i in by["rtl_direction_missing"]] == ["ar"]
    assert [i["file"] for i in by["category_page_unused"]] == ["content/categories/old-family/_index.md"]
    assert {i["link"] for i in by["slash_redirect_temporary"]} == {"/b", "/tags"}
    assert {f["check"] for f in report["findings"]} >= set(by)


def test_menu_ids_the_menu_script_cannot_use(tmp_path):
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", str(repo))
    (repo / "config.yml").write_text(
        "params:\n  dynamicmenuid:\n    en: shop-en\n    zh: shop-zh\n    zh-hant: shop-zh-hant\n    zh-tw: shop-zh\n"
        "languages:\n  en: {languageCode: en}\n  zh: {languageCode: zh}\n  zh-hant: {languageCode: zh-hant}\n"
        "  zh-tw: {languageCode: zh-tw}\n  vi: {languageCode: vi}\n", encoding="utf-8")
    (repo / "content").mkdir()
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "x")
    by = {}
    for i in run(repo)["hosts"][HOST]["issues"]:
        by.setdefault(i["check"], []).append(i)
    assert [(i["link"], i["fix"]) for i in by["menu_id_invalid"]] == [("zh-hant", "shop-zht")]
    assert [i["link"] for i in by["menu_id_missing"]] == ["vi"]
    assert [i["link"] for i in by["menu_id_wrong_script"]] == ["zh-tw"]


def test_llms_txt_missing_the_newest_posts(tmp_path):
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", str(repo))
    ok = "seoTitle: A post title that is long enough\ndescription: " + "d" * 60 + "\n"
    for i, date in enumerate(("2026-01-01", "2026-02-01", "2026-03-01")):
        d = repo / f"content/Blog/p{i}"
        d.mkdir(parents=True)
        (d / "index.md").write_text(f"---\n{ok}date: {date}\nurl: /p{i}/\n---\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "x")
    llms = f"# Blog\n\n- [One](https://{HOST}/p0/): x\n- [Two](https://{HOST}/p1/): y\n".encode()

    class Llms(FakeFetcher):
        def get(self, url, headers=None):
            self.requests += 1
            if url.endswith("/llms.txt"):
                return FetchResult(url, 200, final_url=url, body=llms)
            return FetchResult(url, 404, final_url=url)

    items = [i for i in run(repo, Llms())["hosts"][HOST]["issues"] if i["check"] == "llms_txt_outdated"]
    assert [i["link"] for i in items] == [f"https://{HOST}/p2/"]  # lists 2, the newest 2 are p2 and p1
