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
        return FetchResult(url, self.live.get(url, 404), final_url=url)


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
