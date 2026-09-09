#!/usr/bin/env python3
"""Publish generated reports to a separate, append-only Git history in CI."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def publish(source: Path, repository: Path) -> str:
    result = json.loads((source / "results.json").read_text())
    if result["status"] != "PASS":
        raise ValueError("Only passing verification evidence can be published")
    expected = [source / "figures" / name for name in ("uart-waveforms.png", "spi-modes.png", "fault-detection.png")]
    if not all(p.is_file() for p in expected):
        raise ValueError("All three generated evidence plots are required")
    env = os.environ.copy()
    env.update(GIT_AUTHOR_NAME="github-actions[bot]", GIT_COMMITTER_NAME="github-actions[bot]",
               GIT_AUTHOR_EMAIL="41898282+github-actions[bot]@users.noreply.github.com",
               GIT_COMMITTER_EMAIL="41898282+github-actions[bot]@users.noreply.github.com")

    def git(*args, content=None):
        return subprocess.run(["git", *args], cwd=repository, env=env, input=content,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout.decode().strip()

    # Do not alter the main checkout, index or history. Do not force-push.
    remote = git("ls-remote", "--heads", "origin", "refs/heads/evidence")
    parent = []
    if remote:
        git("fetch", "origin", "refs/heads/evidence")
        parent = ["-p", git("rev-parse", "FETCH_HEAD")]
    readme = ("# UART/SPI verification evidence\n\n"
              "Project owner: **Atul Biju Pillai**. These plots are generated from executed RTL simulations.\n\n"
              "[Design and run instructions](https://github.com/AtulBPillai/uart-spi-verification-lab) · "
              f"[Source commit](https://github.com/AtulBPillai/uart-spi-verification-lab/commit/{result['commit']})\n\n"
              "![UART framing and receive waveform](figures/uart-waveforms.png)\n\n"
              "![All four SPI clock modes](figures/spi-modes.png)\n\n"
              "![Seeded fault detection](figures/fault-detection.png)\n\n" + (source / "SUMMARY.md").read_text())
    files = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob("*")
             if p.is_file() and p.suffix in (".json", ".log", ".txt", ".md", ".png", ".vcd")
             and "mutants" not in p.relative_to(source).parts}
    files["README.md"] = readme.encode()
    with tempfile.TemporaryDirectory() as tmp:
        env["GIT_INDEX_FILE"] = str(Path(tmp) / "index")
        git("read-tree", "--empty")
        for name, content in sorted(files.items()):
            sha = git("hash-object", "-w", "--stdin", content=content)
            git("update-index", "--add", "--cacheinfo", "100644", sha, name)
        tree = git("write-tree")
        commit = git("commit-tree", tree, *parent, "-m", f"Publish verified RTL evidence for {result['commit'][:12]}")
        git("push", "origin", f"{commit}:refs/heads/evidence")
    return commit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("build/evidence"))
    args = parser.parse_args()
    print("Published evidence commit", publish(args.source.resolve(), Path.cwd()))
