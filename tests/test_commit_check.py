"""Offline tests for scripts/commit_check.py: a tiny git repo, no Hugo build."""

import importlib.util
import subprocess
from pathlib import Path

spec = importlib.util.spec_from_file_location("commit_check", Path(__file__).parents[1] / "scripts/commit_check.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def commit(repo, files, msg):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", msg)


def run(repo, rev="HEAD"):
    r = cc.Repo(str(repo), rev)
    r.rev = r.git("rev-parse", rev).strip()
    base = cc.resolve_base(r, None, None)
    changed = r.git("diff", "--name-only", "--diff-filter=d", base, r.rev).splitlines()
    res = cc.Result()
    configs = cc.check_configs(r, res)
    cc.check_redirects(r, base, "blog.example.com", res)
    cc.check_front_matter(r, changed, res)
    cc.check_shortcodes(r, changed, res)
    return res, configs


def setup(tmp_path):
    git(tmp_path, "init", "-q")
    commit(tmp_path, {
        "config.yml": "baseURL: https://blog.example.com/\n",
        "Redirects.json": '{\n "/old/": "https://blog.example.com/new/",\n "/a/": "https://blog.example.com/b/"\n}\n',
        "content/blog/x/2026-01-01-post/index.md": "---\ntitle: T\nurl: /post/\n---\nbody\n",
    }, "start")
    return tmp_path


def test_clean_commit_passes(tmp_path):
    repo = setup(tmp_path)
    commit(repo, {"content/blog/x/2026-01-02-new/index.md": "---\ntitle: N\nurl: /new-post/\n---\n"}, "post")
    res, configs = run(repo)
    assert configs == ["config.yml"]
    assert not res.items and not res.failed


def test_invalid_redirects_and_bad_keys_fail(tmp_path):
    repo = setup(tmp_path)
    commit(repo, {"Redirects.json": '{\n "/old/": "https://blog.example.com/new/",\n'
                  ' "blog.example.com/p/{{ revealButtonHref }}": "http://blog.example.com/p/"\n'
                  ' "/self/": "https://blog.example.com/self/"\n}\n'}, "bad")
    res, _ = run(repo)
    assert res.failed
    assert set(res.items) == {"redirects_invalid", "redirect_key_malformed", "redirect_target_bad",
                              "redirect_self_loop"}
    assert "raw template text" in res.items["redirect_key_malformed"][0]


def test_old_bad_entries_are_not_reported_again(tmp_path):
    repo = setup(tmp_path)
    commit(repo, {"Redirects.json": '{\n "/self/": "https://blog.example.com/self/"\n}\n'}, "old loop")
    commit(repo, {"content/blog/x/2026-01-02-new/index.md": "---\ntitle: N\nurl: /n/\n---\n"}, "post")
    res, _ = run(repo)
    assert not res.items


def test_config_and_front_matter(tmp_path):
    repo = setup(tmp_path)
    commit(repo, {"config.yml": "baseURL: [oops\n",
                  "content/blog/x/2026-01-02-new/index.de.md": "---\ntitle: N\nurl: de/n/\n---\n",
                  "content/blog/x/2026-01-03-bad/index.md": "title: no block\n"}, "bad")
    res, _ = run(repo)
    assert res.failed and "config_invalid" in res.items
    assert len(res.items["front_matter_broken"]) == 1 and len(res.items["url_relative"]) == 1


def test_deleted_post_is_ignored(tmp_path):
    repo = setup(tmp_path)
    git(repo, "rm", "-q", "content/blog/x/2026-01-01-post/index.md")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "delete")
    res, _ = run(repo)
    assert not res.items


EN = '---\ntitle: T\n---\n{{< figure src="a.png" caption="A" >}}\n```cs\nvar s = \\"x\\";\n```\n'


def test_damaged_shortcode_in_translation_fails(tmp_path):
    repo = setup(tmp_path)
    commit(repo, {"content/blog/x/2026-01-02-p/index.md": EN}, "en")
    commit(repo, {"content/blog/x/2026-01-02-p/index.fa.md": EN.replace('"A" >}}', '"A"} >}}'),
                  "content/blog/x/2026-01-02-p/index.de.md": EN.replace("```cs\n", "```cs\n```\n"),
                  "content/blog/x/2026-01-02-p/index.fr.md": EN}, "translations")
    res, _ = run(repo)
    assert res.failed
    assert [w.split(":")[0].rsplit("/", 1)[1] for w in res.items["shortcode_damaged"]] == ["index.fa.md"]
    assert "stray } before >}}" in res.items["shortcode_damaged"][0]
    assert len(res.items["code_fence_mismatch"]) == 1 and "index.de.md" in res.items["code_fence_mismatch"][0]


def test_unbalanced_shortcode_in_english_fails(tmp_path):
    repo = setup(tmp_path)
    commit(repo, {"content/blog/x/2026-01-02-p/index.md": "---\ntitle: T\n---\n{{< figure src=a.png\n"}, "en")
    res, _ = run(repo)
    assert "shortcode_damaged" in res.items


def test_key_problem():
    assert cc.key_problem("/ok/path/") is None
    assert cc.key_problem("blog.example.com/x") == "host or scheme in the key"
    assert cc.key_problem("/x//y") == "double slash"
