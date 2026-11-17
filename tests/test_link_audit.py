"""Link auditor: links read from a Hugo repo, classified against the sitemap inventory and live checks. Offline."""

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.audit.links import LinkAudit, import_report, internal_links, read_post  # noqa: E402
from core.audit.store import AuditStore  # noqa: E402
from core.discovery.fetch import FetchResult  # noqa: E402
from core.discovery.store import InventoryStore  # noqa: E402
from core.findings import FindingsStore  # noqa: E402
from core.prioritize import TrafficIndex, finding_traffic  # noqa: E402
from core.scorecard import group_of  # noqa: E402
from core.tenant import Tenant  # noqa: E402

HOST = "blog.example.cloud"


def make_tenant(repo, supported=("ru", "de")):
    raw = {
        "property": "example.cloud", "languages": ["en", "ru", "de", "cs"],
        "translation_languages": list(supported),
        "hosts": [{"host": HOST, "local_path": str(repo), "fix_channel": "git-pr"}],
        "audit": {"default_lang": "en", "links": {"translation_commits": "^Translate articles for"}},
    }
    return Tenant(property="example.cloud", gsc_properties=[f"https://{HOST}/"], ga4_property_id=None,
                  hosts=raw["hosts"], excluded_host_patterns=[], raw=raw)


class FakeFetcher:
    def __init__(self, live):
        self.live, self.requests, self.asked = live, 0, []

    def get(self, url, headers=None):
        self.requests += 1
        self.asked.append(url)
        got = self.live.get(url, 404)
        if isinstance(got, str):  # a redirect to this URL, which answers 200
            return FetchResult(url, 200, final_url=got, redirects=[url], redirect_statuses=[301])
        return FetchResult(url, got, final_url=url)


def post(folder: Path, name: str, url: str, body: str, eol: str = "\n"):
    folder.mkdir(parents=True, exist_ok=True)
    text = f"---\ntitle: x\nurl: {url}\ndraft: false\n---\n{body}\n"
    (folder / name).write_text(text.replace("\n", eol), encoding="utf-8")


def make_repo(tmp: Path) -> Path:
    c = tmp / "repo" / "content" / "Blog"
    # new post, translated into ru and de
    post(c / "pdf/2026-new", "index.md", "/pdf/new-post/",
         "See [old](https://blog.example.cloud/pdf/old-post/), [other](/words/other-post/), "
         "[full](https://blog.example.cloud/pdf/convert-excel-to-csv-in-nodejs/) and "
         "[gone](/pdf/removed-post/).\n```\nhttps://blog.example.cloud/pdf/in-code/\n```")
    post(c / "pdf/2026-new", "index.ru.md", "/ru/pdf/new-post/",
         "См. [old](https://blog.example.cloud/ru/pdf/old-post/), [other](/words/other-post/), "
         "[cut](https://blog.example.cloud/ru/pdf/convert-excel-to-csv-in-/) и [gone](/ru/pdf/removed-post/).\n"
         "[9]: https://blog.example.cloud/ru//pdf/old-post/\n![img](/ru/pdf/new-post/image.png)")
    post(c / "pdf/2026-new", "index.de.md", "/de/pdf/new-post/", "[ok](/de/words/other-post/)", eol="\r")
    # old post: English only (deliberately not translated)
    post(c / "pdf/2016-old", "index.md", "/pdf/old-post/", "Old text.")
    # translated post missing de
    post(c / "words/2020-other", "index.md", "/words/other-post/", "x")
    post(c / "words/2020-other", "index.ru.md", "/ru/words/other-post/", "x")
    post(c / "words/2020-other", "index.de.md", "/de/words/other-post/", "x")
    post(c / "pdf/2022-full", "index.md", "/pdf/convert-excel-to-csv-in-nodejs/", "x")
    post(c / "pdf/2023-partial", "index.md", "/pdf/partial/", "x")
    post(c / "pdf/2023-partial", "index.ru.md", "/ru/pdf/partial/", "x")
    post(c / "pdf/2024-draft", "index.md", "/pdf/draft/", "[x](/pdf/nowhere/)")
    (c / "pdf/2024-draft" / "index.md").write_text("---\nurl: /pdf/draft/\ndraft: true\n---\n[x](/pdf/nowhere/)\n")
    return tmp / "repo"


def inventory(paths) -> sqlite3.Connection:
    store = InventoryStore(":memory:")
    run = store.start_run("example.cloud", {})
    rows = []
    for p in paths:
        lang = p.split("/")[1] if p.split("/")[1] in ("ru", "de", "cs") else "en"
        rows.append((run, f"https://{HOST}{p}", HOST, "", lang, "post", None, "s.xml", 0))
    store.add_urls(rows)
    return store.db


SITEMAP = ["/", "/ru/", "/de/", "/cs/", "/pdf/new-post/", "/ru/pdf/new-post/", "/de/pdf/new-post/",
           "/pdf/old-post/", "/words/other-post/", "/ru/words/other-post/", "/de/words/other-post/",
           "/pdf/convert-excel-to-csv-in-nodejs/", "/pdf/partial/", "/ru/pdf/partial/"]


def run_audit(tmp, live=None, **kw):
    repo = make_repo(tmp)
    fetcher = FakeFetcher(live or {})
    a = LinkAudit(make_tenant(repo), fetcher, AuditStore(":memory:"), inventory(SITEMAP), blame=False, log=None,
                  **kw)
    return a, a.run(), fetcher


def test_read_post_normalizes_cr_line_endings(tmp_path):
    f = tmp_path / "index.de.md"
    f.write_text("---\rurl: /de/a/\rdraft: false\r---\rText [x](/de/b/)\r", encoding="utf-8")
    url, draft, text, start = read_post(f)
    assert (url, draft) == ("/de/a/", False)
    assert internal_links(text, start, HOST) == [("/de/b/", "/de/b/", 5)]


def test_links_skip_code_files_and_other_hosts():
    text = ("---\nurl: /a/\n---\n[a](https://blog.example.cloud/x/) [b](https://other.com/y/) `[c](/code/)`\n"
            "```\n[d](/in-fence/)\n```\n[e](/pic.png) <a href=\"/html-link\">h</a>\n[1]: /ref-link/ \"T\"\n"
            "[f](/a/images/result.csv) [g](/b/input.TSV) [h](/c/run-in-node.js/) [i](/d/words-for-.net)\n")
    links = [p for _, p, _ in internal_links(text, text.index("---\n", 4) + 4, HOST)]
    assert links == ["/x/", "/html-link/", "/ref-link/", "/c/run-in-node.js/", "/d/words-for-.net/"]


def test_static_html_file_and_relative_post_url(tmp_path):
    repo = make_repo(tmp_path)
    c = repo / "content" / "Blog" / "pdf/2025-static"
    post(c, "index.md", "/pdf/static/", "[demo](/viewer/demo.html) [gone](/viewer/gone.html)")
    post(c, "index.ru.md", "ru/pdf/static/", "[gone](/ru/pdf/removed-post/)")
    fetcher = FakeFetcher({f"https://{HOST}/viewer/demo.html": 200})
    a = LinkAudit(make_tenant(repo), fetcher, AuditStore(":memory:"), inventory(SITEMAP), blame=False, log=None)
    issues = a.run()["hosts"][HOST]["issues"]
    assert [i["link"] for i in issues if i["file"].endswith("2025-static/index.md")] == ["/viewer/gone.html"]
    # Hugo publishes a url without a leading slash under the language
    assert {i["page"] for i in issues if i["file"].endswith("2025-static/index.ru.md")} == {
        f"https://{HOST}/ru/ru/pdf/static/"}


def test_classifies_every_kind(tmp_path):
    a, report, fetcher = run_audit(tmp_path)
    issues = {(i["lang"], i["link"]): i for i in report["hosts"][HOST]["issues"]}
    # prefix added, no ru translation: points at the English post
    i = issues[("ru", "https://blog.example.cloud/ru/pdf/old-post/")]
    assert i["check"] == "link_missing_translation" and i["fix"] == f"https://{HOST}/pdf/old-post/"
    # English link although the ru translation exists
    i = issues[("ru", "/words/other-post/")]
    assert i["check"] == "link_wrong_language" and i["fix"] == f"https://{HOST}/ru/words/other-post/"
    # cut-off slug, repaired from the original post's full link (no ru translation -> English)
    i = issues[("ru", "https://blog.example.cloud/ru/pdf/convert-excel-to-csv-in-/")]
    assert i["check"] == "link_damaged" and i["fix"] == f"https://{HOST}/pdf/convert-excel-to-csv-in-nodejs/"
    # double slash, repaired
    i = issues[("ru", "https://blog.example.cloud/ru//pdf/old-post/")]
    assert i["check"] == "link_damaged" and i["fix"] == f"https://{HOST}/pdf/old-post/"
    # broken in the original too: copied
    assert issues[("ru", "/ru/pdf/removed-post/")]["note"].startswith("same broken link")
    assert issues[("en", "/pdf/removed-post/")]["check"] == "link_broken"
    # fine: de page (CR line endings) links its own language; images, code and drafts are skipped
    assert not [k for k in issues if k[0] == "de"]
    assert not any("in-code" in k[1] or "nowhere" in k[1] or "image" in k[1] for k in issues)
    # targets in the sitemaps are never fetched
    assert not {f"https://{HOST}{p}" for p in SITEMAP} & set(fetcher.asked)
    assert len(fetcher.asked) == len(set(fetcher.asked))  # each target fetched once


def test_copied_broken_link_is_one_location_under_the_english_post(tmp_path):
    # SK, 2026-11-17: say the English post has the bad link and N translations copied it
    _, report, _ = run_audit(tmp_path)
    f = next(f for f in report["findings"] if f["check"] == "link_broken")
    locs = [loc for loc in f["evidence"]["locations"] if "removed-post" in loc["url"]]
    assert len(locs) == 1
    assert locs[0]["origin"] == "english" and locs[0]["copies"] == 1 and locs[0]["copy_langs"] == ["ru"]
    assert locs[0]["file"].endswith("/index.md")


def test_broken_link_suggestions_only_when_certain(tmp_path):
    # 17 Nov 2026, blog.conholdate.com: wrong slugs in English posts, copied by 17 translations
    a = LinkAudit(make_tenant(tmp_path), FakeFetcher({}), AuditStore(":memory:"), inventory([]), blame=False, log=None)
    known = {"/total/find-synonyms-in-java/", "/total/find-synonym-in-csharp/", "/total/convert-excel-to-pdf-using-java/",
             "/total/convert-xml-to-pdf-in-java/", "/ru/total/find-synonyms-in-java/",
             "/total/create-ms-word-documents-in-csharp/", "/total/a-b-in-java/", "/total/a-b-using-java/"}
    assert a.suggest("/total/find-synonym-in-java/", "en", known, []) == (
        "/total/find-synonyms-in-java/", "existing post with the same words")
    assert a.suggest("/total/find-synonym-in-java/", "ru", known, [])[0] == "/ru/total/find-synonyms-in-java/"
    assert a.suggest("/total/convert-excel-to-pdf-in-java/", "en", known, [])[0] == \
        "/total/convert-excel-to-pdf-using-java/"  # never the xml post: other words
    assert a.suggest("/total/a-b-for-java/", "en", known, []) == (None, "")  # two posts with the same words: no guess
    assert a.suggest("/total/convert-pdf-to-excel-in-java/", "en", known, []) == (None, "")  # other order
    assert a.suggest("/total/find-synonym-in-java/", "de", known, [])[0] == "/total/find-synonyms-in-java/"  # no de
    assert a.suggest("/total/never-existed/", "en", known, []) == (None, "")
    # a translation changed a word: the English original links the right page
    assert a.suggest("/total/create-ms-PDF-documents-in-csharp/", "de", known,
                     ["/total/create-ms-word-documents-in-csharp/"]) == (
        "/total/create-ms-word-documents-in-csharp/", "the English post links this page")


def test_old_english_slug_in_a_translation_follows_the_redirect(tmp_path):
    # 17 Nov 2026: th/tr/vi linked /<lang>/total/<old slug>/; the English old slug redirects to a page that IS translated
    from core.audit.links import Post
    old, new = f"https://{HOST}/pdf/old-slug/", "https://blog.example.cloud/pdf/new-slug/"
    a = LinkAudit(make_tenant(tmp_path), FakeFetcher({old: new}), AuditStore(":memory:"), inventory([]), blame=False,
                  log=None)
    p = Post(Path("x"), "x", "f", "ru", "/ru/pdf/a/", "", 0)
    assert a.classify(HOST, p, "/ru/pdf/old-slug/", {"/pdf/new-slug/", "/ru/pdf/new-slug/"}, []) == (
        "link_redirected", "/ru/pdf/new-slug/", "old URL; /pdf/old-slug/ redirects to /pdf/new-slug/")
    # not translated yet: the English current page, and the missing translation is named
    assert a.classify(HOST, p, "/ru/pdf/old-slug/", {"/pdf/new-slug/"}, []) == (
        "link_missing_translation", "/pdf/new-slug/", "no ru translation of /pdf/new-slug/")


def test_history_tells_translation_introduced_it_or_is_out_of_date(tmp_path):
    # SK, 2026-11-17: for a bad link only translations have, was the English post changed after the translation?
    import os
    import subprocess

    from core.audit.links import Post

    repo = tmp_path / "r"
    (repo / "content/p").mkdir(parents=True)

    def commit(msg, date):
        env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        for args in (["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@e.x", "commit", "-qm", msg]):
            subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)

    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    en, ru = repo / "content/p/index.md", repo / "content/p/index.ru.md"
    en.write_text("---\nurl: /p/\n---\n[1]: /pdf/right/\n[2]: /pdf/old/\n", encoding="utf-8")
    commit("english", "2023-03-03T10:00:00")
    ru.write_text("---\nurl: /ru/p/\n---\n[1]: /ru/pdf/wrong/\n[2]: /ru/pdf/old/\n", encoding="utf-8")
    commit("translation", "2023-03-06T10:00:00")
    en.write_text("---\nurl: /p/\n---\n[1]: /pdf/right/\n[2]: /pdf/new/\n", encoding="utf-8")
    commit("english link changed", "2024-01-01T10:00:00")
    a = LinkAudit(make_tenant(repo), FakeFetcher({}), AuditStore(":memory:"), inventory([]), log=None)
    posts = {lg: Post(f, f"content/p/{f.name}", "content/p", lg, "/", f.read_text(encoding="utf-8"), 0)
             for lg, f in (("en", en), ("ru", ru))}
    issues = [{"check": "link_broken", "lang": "ru", "file": "content/p/index.ru.md", "link": "/ru/pdf/wrong/",
               "fix": f"https://{HOST}/ru/pdf/right/"},
              {"check": "link_broken", "lang": "ru", "file": "content/p/index.ru.md", "link": "/ru/pdf/old/",
               "fix": f"https://{HOST}/ru/pdf/new/"}]
    a.add_history(HOST, issues, {"content/p": posts})
    assert issues[0]["history"]["english_newer"] is False  # English line older: the translation introduced it
    assert issues[0]["history"]["translated"] == "2023-03-06"
    assert issues[1]["history"]["english_newer"] is True  # English changed later: translation out of date
    assert issues[1]["history"]["english_line"] == "2024-01-01"


def test_live_200_outside_the_sitemap_is_fine(tmp_path):
    _, report, _ = run_audit(tmp_path, live={f"https://{HOST}/pdf/removed-post/": 200,
                                             f"https://{HOST}/ru/pdf/removed-post/": 200})
    assert not [i for i in report["hosts"][HOST]["issues"] if "removed-post" in i["link"]]


def test_unchecked_targets_are_not_reported(tmp_path):
    _, report, fetcher = run_audit(tmp_path, max_live=0)
    assert fetcher.requests == 0
    checks = {i["check"] for i in report["hosts"][HOST]["issues"]}
    assert checks == {"link_wrong_language"}  # needs no request; everything else stays unchecked


def test_translation_sets(tmp_path):
    _, report, _ = run_audit(tmp_path)
    r = report["hosts"][HOST]
    assert [p["folder"] for p in r["partial"]] == ["content/Blog/pdf/2023-partial"]
    assert r["partial"][0]["missing"] == ["de"]
    assert r["unsupported"] == {"cs": 1}


def test_findings_one_per_check_with_exact_pages(tmp_path):
    _, report, _ = run_audit(tmp_path)
    by = {f["check"]: f for f in report["findings"]}
    assert set(by) == {"link_missing_translation", "link_damaged", "link_wrong_language", "link_broken",
                       "translation_partial", "language_unsupported"}
    f = by["link_damaged"]
    assert f["evidence"]["urls"] == [f"https://{HOST}/ru/pdf/new-post/"] and f["affected_pages"] == 1
    assert f["template"] == "post" and "2 links on 1 pages" in f["evidence"]["observed"]
    assert "0 written by translation commits" in f["evidence"]["observed"]
    assert by["language_unsupported"]["evidence"]["urls"] == [f"https://{HOST}/cs/"]
    assert group_of(by["link_broken"]) == "internal links" and group_of(by["translation_partial"]) == "translations"
    # exact pages: the Prioritizer counts only the affected pages' traffic
    idx = TrafficIndex.build(make_tenant(Path("/x")), [{"page": f"https://{HOST}/ru/pdf/new-post/", "clicks": 7,
                                                          "impressions": 100}])
    f["source"] = "link-audit"
    assert finding_traffic(f, idx)["clicks_28d"] == 7


def test_import_resolves_fixed_links(tmp_path):
    _, report, _ = run_audit(tmp_path)
    store = FindingsStore(":memory:")
    import_report(store, report)
    assert len(store.findings()) == 6
    report2 = dict(report, run_id=report["run_id"] + 1,
                   findings=[f for f in report["findings"] if f["check"] != "link_damaged"])
    changes = import_report(store, report2)
    assert len(changes["resolved"]) == 1


def test_blame_names_the_translation_commit(tmp_path):
    import subprocess
    repo = make_repo(tmp_path)
    git = ["git", "-C", str(repo), "-c", "user.name=T", "-c", "user.email=t@x"]
    if subprocess.run(["git", "--version"], capture_output=True).returncode:
        return
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", 'Translate articles for: "New post"'], check=True)
    a = LinkAudit(make_tenant(repo), FakeFetcher({}), AuditStore(":memory:"), inventory(SITEMAP), log=None)
    report = a.run()
    ru = [i for i in report["hosts"][HOST]["issues"] if i["lang"] == "ru"]
    assert ru and all(i["by_translation_commit"] for i in ru)
    assert all(" T:" not in i["commit"] and "Translate articles for" in i["commit"] for i in ru)  # no author
    assert report["hosts"][HOST]["repo"]["commit"]
    # the report lays out each link's page, file, line, fix and commit on separate lines
    loc = next(loc for f in report["findings"] for loc in f["evidence"]["locations"] if loc["role"] == "link")
    assert {"page", "file", "line", "fix", "commit"} <= set(loc) and "note" not in loc
    assert re.match(r"^[0-9a-f]{8} \d{4}-\d{2}-\d{2}: ", loc["commit"])  # the format the report splits


def test_link_that_redirects_is_an_old_url_with_the_target_as_fix(tmp_path):
    """SK, 2026-11-06: a link that works only through a redirect is reported (old URL), fix = the target, in the
    page's language when that exists; a redirect to another host or to the same path is not an old URL."""
    _, report, _ = run_audit(tmp_path, live={
        f"https://{HOST}/pdf/removed-post/": f"https://{HOST}/words/other-post/",
        f"https://{HOST}/ru/pdf/removed-post/": f"https://{HOST}/words/other-post/"})
    issues = {(i["lang"], i["link"]): i for i in report["hosts"][HOST]["issues"]}
    en, ru = issues[("en", "/pdf/removed-post/")], issues[("ru", "/ru/pdf/removed-post/")]
    assert en["check"] == ru["check"] == "link_redirected"
    assert en["fix"] == f"https://{HOST}/words/other-post/" and ru["fix"] == f"https://{HOST}/ru/words/other-post/"
    assert en["note"] == "redirects to /words/other-post/"
    assert [f["check"] for f in report["findings"] if f["check"] == "link_redirected"] == ["link_redirected"]
    _, report, _ = run_audit(tmp_path / "b", live={f"https://{HOST}/pdf/removed-post/": "https://other.com/x/"})
    assert not [i for i in report["hosts"][HOST]["issues"] if i["link"] == "/pdf/removed-post/"]
