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
    H = "https://blog.example.com/"
    assert key_problem("/notify-one_deny?aHR0c", H + "x/").startswith("query string")
    home = "redirects to the home page (soft 404)"
    assert key_problem("/login", H) == key_problem("/cart/smart-wagon", "https://blog.example.com") == home
    assert key_problem("/feed/", H + "index.xml") is None and key_problem("/", H) is None
    assert key_problem("/about", "https://about.example.com/", "blog.example.com") is None  # another site
    assert key_problem("/RU/tOTal/Post/", H + "ru/total/post/") == "upper-case copy of its target"
    assert key_problem("/JPG-Image.jpg", H + "total/a/images/JPG-Image.jpg") is None  # case kept, different path


def test_invalid_file_is_still_read_line_by_line():
    assert json_error(GOOD) is None and "line 7" in json_error(BAD)
    assert [p[1] for p in parse_pairs(BAD)][-2:] == ["blog.example.com/a/{{ token }}", "http://blog.example.com/b"]


def test_finds_every_kind_and_names_the_commit(tmp_path):
    report = run(make_repo(tmp_path))
    checks = {f["check"]: f for f in report["findings"]}
    checks.pop("post_text_untranslated")  # the fixture's translations copy the English seoTitle: right to flag
    checks.pop("post_body_cut_off", None)  # fixture bodies are one word without a full stop: right to flag
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


def test_tag_category_and_url_parts_that_cannot_be_opened(tmp_path):
    # blog.groupdocs.cloud, 26 Nov 2026 (found by Shoaib Khan): '.NET …' tags 404 live, 'c# …' tags are cut at '#',
    # escaped \"x\" tags get backslash slugs
    repo = make_repo(tmp_path)
    post = repo / "content/Blog/pdf/2026-01-03-d"
    post.mkdir(parents=True)
    (post / "index.md").write_text("---\ntitle: d\nurl: /pdf/d/\ntags: ['.NET rewriter SDK', 'c# ai summary', 'pdf', "
                                   "'C# .NET']\ncategories: ['Pdf Family']\n---\n", encoding="utf-8")
    (post / "index.de.md").write_text('---\ntitle: d\nurl: /de/.net/d/\ntags:\n- \\"pdf\\"\n'
                                      'categories:\n- \\"Pdf Family\\"\n---\n', encoding="utf-8")
    audit = RepoAudit(make_tenant(repo), FakeFetcher(), AuditStore(":memory:"), sample=0, log=None)
    got = sorted((i["file"].rsplit("/", 1)[-1], i["note"]) for i in audit.check_posts(HOST)[0]
                 if i["check"] == "url_part_unsafe")
    assert got == [("index.de.md", "category '\\\\\"Pdf Family\\\\\"': holds a backslash or quotes"),
                   ("index.de.md", "post url: starts with a dot"),
                   ("index.de.md", "tag '\\\\\"pdf\\\\\"': holds a backslash or quotes"),
                   ("index.md", "tag '.NET rewriter SDK': starts with a dot"),
                   ("index.md", "tag 'C# .NET': holds #"),
                   ("index.md", "tag 'c# ai summary': holds #")]


def test_translation_tags_and_category_must_be_the_english_ones(tmp_path):
    # blog.groupdocs.cloud, 26 Nov 2026: tags and categories are never translated; some translations had them
    # translated, missing, or under a translated key ('теги:') that Hugo ignores
    repo = make_repo(tmp_path)
    post = repo / "content/Blog/pdf/2026-01-04-e"
    post.mkdir(parents=True)
    (post / "index.md").write_text("---\ntitle: e\nurl: /pdf/e/\ntags: [pdf, merge]\ncategories: [Pdf Family]\n---\n",
                                   encoding="utf-8")
    for lang, fm in {"de": "tags: [pdf, merge]\ncategories: [Pdf Family]",  # fine
                     "fr": "tags: [pdf, fusionner]\ncategories: [Famille Pdf]",
                     "ru": "теги: [pdf, merge]\ncategories: [Pdf Family]"}.items():
        (post / f"index.{lang}.md").write_text(f"---\ntitle: e\nurl: /{lang}/pdf/e/\n{fm}\n---\n", encoding="utf-8")
    audit = RepoAudit(make_tenant(repo), FakeFetcher(), AuditStore(":memory:"), sample=0, log=None)
    got = sorted((i["file"].rsplit("/", 1)[-1], i["note"]) for i in audit.check_posts(HOST)[0]
                 if i["check"] == "translation_taxonomy_differs")
    assert got == [("index.fr.md", "tags differ; category 'Famille Pdf'"),
                   ("index.ru.md", "translated key теги (Hugo ignores it); tags missing")]


def test_two_posts_on_one_url_and_body_h1(tmp_path):
    # blog.conholdate.com, 16 Nov 2026: two folders with the same url (one never published); '# Title' in the body
    repo = make_repo(tmp_path)
    for folder, body in (("2025-01-01-c", "# Same Title\n\nText\n```\n# a shell comment\n```\n    # indented code\n"),
                         ("2026-01-01-c", "Text\n\n## Fine\n<h1 class=x>Also an H1</h1>\n")):
        post = repo / "content/Blog/pdf" / folder
        post.mkdir(parents=True)
        (post / "index.md").write_text(f"---\ntitle: c\nurl: /pdf/c/\n---\n{body}", encoding="utf-8")
        (post / "index.de.md").write_text("---\ntitle: c\nurl: /de/pdf/c/\n---\nText\n", encoding="utf-8")
    audit = RepoAudit(make_tenant(repo), FakeFetcher(), AuditStore(":memory:"), sample=0, log=None)
    issues = audit.check_posts(HOST)[0]
    dup = [(i["file"], i["link"], i["note"]) for i in issues if i["check"] == "post_url_duplicate"]
    assert dup == [("content/Blog/pdf/2025-01-01-c/index.de.md", "/de/pdf/c/", "same URL as 2026-01-01-c"),
                   ("content/Blog/pdf/2026-01-01-c/index.de.md", "/de/pdf/c/", "same URL as 2025-01-01-c"),
                   ("content/Blog/pdf/2025-01-01-c/index.md", "/pdf/c/", "same URL as 2026-01-01-c"),
                   ("content/Blog/pdf/2026-01-01-c/index.md", "/pdf/c/", "same URL as 2025-01-01-c")]
    h1 = [(i["file"].split("/")[-2], i["line"], i["note"]) for i in issues if i["check"] == "post_body_h1"]
    assert h1 == [("2025-01-01-c", 5, "# Same Title"), ("2026-01-01-c", 8, "<h1 class=x>Also an H1</h1>")]


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
    llms = f"# Blog\n\n- [One](https://{HOST}/p0/): x\n- [Two](https://{HOST}/p1/): y\n- [日本語 (ja)](https://{HOST}/ja/)\n".encode()

    class Llms(FakeFetcher):
        def get(self, url, headers=None):
            self.requests += 1
            if url.endswith("/llms.txt"):
                return FetchResult(url, 200, final_url=url, body=llms, headers={"content-type": "text/plain"})
            return FetchResult(url, 404, final_url=url)

    items = [i for i in run(repo, Llms())["hosts"][HOST]["issues"] if i["check"] == "llms_txt_outdated"]
    assert [i["link"] for i in items] == [f"https://{HOST}/p2/"]  # lists 2, the newest 2 are p2 and p1
    issues = run(repo, Llms())["hosts"][HOST]["issues"]
    assert [i["check"] for i in issues if i["check"] == "llms_txt_charset"] == ["llms_txt_charset"]
    # 26 Nov 2026: "## Most read" first, then "## Newest": only the Newest section must hold the newest posts
    llms = (f"# Blog\n\n## Most read\n\n- [Old](https://{HOST}/p0/): x\n\n## Newest\n\n"
            f"- [Three](https://{HOST}/p2/): z\n- [Two](https://{HOST}/p1/): y\n").encode()
    items = [i for i in run(repo, Llms())["hosts"][HOST]["issues"] if i["check"] == "llms_txt_outdated"]
    assert items == []


def test_reviewed_old_urls_are_not_junk(tmp_path):
    # SK, 2026-11-13: an old French-slug URL of a moved post really existed; listed in audit.repo.redirect_keep
    old = "/fr/pdf/cr%C3%A9ez-a/"
    other = "/fr/pdf/r%C3%A9sum%C3%A9/"
    entries = {old: f"https://{HOST}/fr/pdf/a/", other: f"https://{HOST}/fr/pdf/a/"}
    repo = make_repo(tmp_path, "{\n" + ",\n".join(f'  "{k}": "{v}"' for k, v in entries.items()) + "\n}\n")
    tenant = make_tenant(repo)
    tenant.raw["audit"]["repo"] = {"redirect_keep": [{"key": "/fr/pdf/créez-a/", "reason": "old URL of a moved post"}]}
    audit = RepoAudit(tenant, FakeFetcher(), AuditStore(":memory:"), log=None)
    issues, _ = audit.check_redirects(HOST)
    junk = [i["link"] for i in issues if i["check"] == "redirect_key_malformed"]
    assert junk == [other]  # the kept key (raw or encoded spelling) is not junk; the other is


def test_iso_date_reads_rfc_and_iso_dates():
    import datetime as dt

    from core.audit.repo import iso_date
    assert iso_date("Thu, 25 Jan 2024 10:00:00 +0000") == "2024-01-25"  # sorted as "Thu, 25 Ja" before
    assert iso_date("2026-11-12T08:00:00Z") == "2026-11-12" and iso_date(dt.date(2026, 11, 13)) == "2026-11-13"
    assert iso_date(dt.datetime(2026, 11, 13, 9, 0)) == "2026-11-13" and iso_date("someday") is None


def test_front_matter_markup():
    # blog.conholdate.com, 18 Nov 2026: '**' in descriptions shows as is in the meta description
    from core.audit.repo import front_matter_markup

    data = {"title": "Convert **PDF** to Word", "seoTitle": "C* and file_name are fine",
            "description": "Use `Document` and [docs](https://x.y/)", "summary": "**shown as bold on cards**",
            "url": "/a/**/"}
    found = {(f, m) for f, m, _ in front_matter_markup(data)}
    assert found == {("title", "**"), ("description", "`, [x](url)")}  # summary only counts without a description
    assert [f for f, _, _ in front_matter_markup({"summary": "a __bold__ word"})] == ["summary"]
    assert front_matter_markup({"title": "Plain", "description": None}) == []


def test_body_cut_off_and_raw_html():
    # blog.conholdate.com, 19 Nov 2026: optimizer cut posts mid-word; **<input>** renders as an empty bold
    from core.audit.repo import body_cut_off, raw_html_dropped

    assert body_cut_off("Intro.\n\n  * Traditional — legacy PK") == "ends with '* Traditional — legacy PK'"
    assert body_cut_off("Text.\n```\ncode {") == "a code block is never closed"
    assert body_cut_off("Done.\n\n [1]: https://x.y/\n") is None
    assert body_cut_off("See:\n{{< gist a b >}}\n") is None
    found = raw_html_dropped("add an **<input>** element\n**`<head>`** ok\n```\n**<b>** in code\n```\n")
    assert [n for n, _ in found] == [1]


def test_cover_lost_and_escaped_values(tmp_path):
    # blog.conholdate.com, 19 Nov 2026: flat cover block (no image live) and \"…\" values
    from core.audit.repo import cover_image, escaped_values

    esc = escaped_values({"title": '\\"Titel\\"', "author": "A", "cover": {"alt": '\\"x\\"'}})
    assert esc == ["title", "cover.alt"]
    assert cover_image({"cover": None, "image": "a.jpg"}) is None
    assert cover_image({"cover": {"image": "a.jpg"}}) == "a.jpg"
    repo = make_repo(tmp_path)
    post = repo / "content/Blog/pdf/2025-01-01-c"
    post.mkdir(parents=True)
    (post / "index.md").write_text('---\ntitle: c\nurl: /pdf/c/\ncover:\n    image: images/c.jpg\n'
                                   '    alt: "C"\n---\nT\n', encoding="utf-8")
    (post / "index.fr.md").write_text('---\ntitle: \\"c fr\\"\nurl: /fr/pdf/c/\ncover:\nimage: images/c.jpg\n'
                                      'légende: \\"C\\"\n---\nT\n', encoding="utf-8")
    audit = RepoAudit(make_tenant(repo), FakeFetcher(), AuditStore(":memory:"), sample=0, log=None)
    found = {i["check"] for i in audit.check_posts(HOST)[0] if i["file"].endswith("index.fr.md")}
    assert {"post_cover_lost", "post_front_matter_escaped"} <= found


def test_garbled_translation_text():
    # blog.conholdate.com, 18 Nov 2026: titles that are the LLM's answer, a description of zero-width characters
    from core.audit.repo import garbled_text

    en = "Convert STL to PDF in C#"
    assert garbled_text("STL'yi PDF'ye dönüştürmek için adımlar:\n1. STL dosyasını yükleyin", en).startswith("several")
    assert garbled_text("Converteer STL" + "​" * 8, en) == "a run of zero-width characters"
    assert "as long" in garbled_text("x" * 150, en)
    assert garbled_text("STL'yi C#'ta PDF'ye Dönüştürün", en) is None
    assert garbled_text("C# で STL を PDF に変換する", en) is None  # CJK counts double, still well under 6x
    assert garbled_text("", en) is None and garbled_text("abc", "") is None


def test_shortcode_shown_as_text(tmp_path):
    # blog.conholdate.com, 17 Nov 2026: '{{ gist … }}' and '{{&lt; figure … &gt;}}' render as text
    from core.audit.repo import shortcodes_as_text

    names = {"figure", "gist", "img_a_blank"}
    body = ('{{< figure src="a.jpg" >}}\n{{ gist org abc "x.cs" }}\n{{&lt; figure src="b.jpg" &gt;}}\n'
            '{{figure src="c.jpg"}}\n```\n{{ gist inside code }}\n```\n`{{ gist inline }}`\n'
            '{{ .Title }} and {{ unknown thing }}\n{{% img_a_blank "u" %}}\n')
    assert [n for n, _ in shortcodes_as_text(body, names)] == [2, 3, 4]
    repo = make_repo(tmp_path)
    post = repo / "content/Blog/pdf/2025-01-01-s"
    post.mkdir(parents=True)
    (post / "index.md").write_text('---\ntitle: s\nurl: /pdf/s/\n---\nText\n{{ gist org abc "x.cs" }}\n',
                                   encoding="utf-8")
    audit = RepoAudit(make_tenant(repo), FakeFetcher(), AuditStore(":memory:"), sample=0, log=None)
    found = [(i["file"], i["line"]) for i in audit.check_posts(HOST)[0] if i["check"] == "post_shortcode_as_text"]
    assert found == [("content/Blog/pdf/2025-01-01-s/index.md", 6)]


def test_fences_that_shift_code_blocks_and_split_link_remainders():
    # blog.groupdocs.cloud, 26 Nov 2026: generator's stray ``` before <!--[CODE_SNIPPET_END]-->, a closing fence glued
    # to its caption, and a translator's split URL ('... -API/)'); a letter's sign-off is a proper ending
    from core.audit.repo import body_cut_off, fence_problems, split_link_remainders

    stray = "Intro\n```bash\npip x\n```\n```\n<!--[CODE_SNIPPET_END]-->\n\nText\n"
    assert [n for n, _ in fence_problems(stray)] == [5]
    glued = "Text\n\n```\ncurl x\n```.NET SDK example\n```\ncode\n```\n"
    assert [n for n, _ in fence_problems(glued)] == [5]
    assert fence_problems("```py\nx\n```\n\n```\ny\n```\n") == []
    assert fence_problems("```\n<repository/>\n```\n```\n<dependency/>\n```\n") == []  # two blocks in a row
    assert [n for n, _ in fence_problems("```\nx\n```\n```\n\n```\n")] == [4]  # stray empty block
    line = "See [the guide](https://b.example/ja/conversion/x-using-rest-api/) を参照してください。 -API/)"
    assert [n for n, _ in split_link_remainders(f"a\n{line}\n")] == [2]
    assert split_link_remainders("See [x](https://b.example/a/) and (/docs/).\n") == []
    assert body_cut_off("We apologize. Kind regards, The GroupDocs Team\n") is None
