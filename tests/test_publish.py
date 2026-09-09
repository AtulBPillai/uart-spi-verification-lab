import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from scripts.publish_evidence import publish


@unittest.skipUnless(shutil.which("git"), "git is required for publication integration test")
class PublicationTests(unittest.TestCase):
    def test_publishes_without_changing_main_and_preserves_evidence_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, repo, evidence = root/"remote.git", root/"repo", root/"reports"

            def git(*args):
                return subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.DEVNULL).decode().strip()

            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            repo.mkdir()
            git("init", "-b", "main")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            (repo/"source.v").write_text("module source; endmodule\n")
            git("add", "source.v")
            git("commit", "-m", "Source")
            head = git("rev-parse", "HEAD")
            git("remote", "add", "origin", str(remote))
            git("push", "-u", "origin", "main")
            (evidence/"figures").mkdir(parents=True)
            # Fixtures validate publication mechanics, not simulation or PNG rendering.
            (evidence/"results.json").write_text(json.dumps(dict(status="PASS", commit=head)))
            (evidence/"SUMMARY.md").write_text("Test fixture\n")
            for name in ("uart-waveforms", "spi-modes", "fault-detection"):
                (evidence/"figures"/f"{name}.png").write_bytes(b"fixture")
            first = publish(evidence, repo)
            second = publish(evidence, repo)
            self.assertEqual(git("rev-parse", "HEAD"), head)
            self.assertEqual(git("status", "--porcelain"), "")
            self.assertEqual(git("rev-parse", f"{second}^"), first)
            self.assertIn("Source commit", git("show", f"{second}:README.md"))
            self.assertEqual(git("ls-remote", "origin", "refs/heads/main").split()[0], head)


if __name__ == "__main__":
    unittest.main()
