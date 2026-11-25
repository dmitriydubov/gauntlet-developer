"""gauntlet/hooks/session_start.sh reads baseRef as everything else reads gauntlet.properties.

gauntlet.gradle loads the file with java.util.Properties, where `=`, `:` or blanks end a key; CI and the Stop hook read
it the same way. The SessionStart hook took only `baseRef=`: with `baseRef: origin/release` it fetched and reported
origin/main, and a cloud session's scoped checks ran against a base branch the clone had never fetched.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import kit


def git(cwd, *args):
    r = kit.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args], cwd=cwd)
    assert r.code == 0, f"git {' '.join(args)}: {r.out}"
    return r.out.strip()


class BaseRef(unittest.TestCase):

    def session_start(self, line):
        """The hook in a cloud session's single-branch clone of main; the base branch `release` is not fetched yet."""
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            os.makedirs(source)
            git(source, "init", "-q", "-b", "main")
            shutil.copytree(os.path.join(kit.kit(), "gauntlet"), os.path.join(source, "gauntlet"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            props = os.path.join(source, "gauntlet", "config", "gauntlet.properties")
            kit.write(props, kit.read(props) + line + "\n")
            # modules a hook must never import from the project directory
            kit.write(os.path.join(source, "stop_gate.py"), "raise SystemExit('the project directory was imported')\n")
            kit.write(os.path.join(source, "re.py"), "raise SystemExit('the project directory was imported')\n")
            git(source, "add", "-A")
            git(source, "commit", "-q", "-m", "base")
            git(source, "branch", "release")
            git(tmp, "clone", "-q", "--bare", source, "origin.git")
            clone = os.path.join(tmp, "clone")
            git(tmp, "clone", "-q", "--single-branch", "--branch", "main", os.path.join(tmp, "origin.git"), clone)
            self.assertNotIn("origin/release", git(clone, "branch", "-r"))
            env = {k: v for k, v in os.environ.items() if not k.startswith(("GAUNTLET_", "CLAUDE_"))}
            env.update(CLAUDE_PROJECT_DIR=clone, CLAUDE_CODE_REMOTE="true", GAUNTLET_DOCKER="off")
            r = subprocess.run(["bash", os.path.join(clone, "gauntlet", "hooks", "session_start.sh")], cwd=clone,
                               input='{"session_id": "s"}', stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               env=env)
            fetched = "origin/release" in git(clone, "branch", "-r")
            bytecode = [d for d, _, _ in os.walk(os.path.join(clone, "gauntlet")) if d.endswith("__pycache__")]
            return r, fetched, bytecode

    def test_separators_java_util_properties_reads(self):
        for line in ("baseRef=origin/release", "baseRef: origin/release", "baseRef origin/release",
                     "baseRef\t:\torigin/release\r", "baseRef = origin/main\nbaseRef:origin/release"):
            with self.subTest(line=line):
                r, fetched, bytecode = self.session_start(line)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("[gauntlet] active - scope: changed vs origin/release;", r.stdout)
                self.assertTrue(fetched, "the hook fetched another branch than baseRef names:\n" + r.stdout)
                self.assertEqual(bytecode, [])          # reading the setting leaves nothing in gauntlet/

    def test_empty_or_absent_value_is_the_default(self):
        # gauntlet.gradle falls back to origin/main for an empty value too
        for line in ("baseRef=origin/release\nbaseRef=", "baseRef=origin/release\nbaseRef", "# baseRef: origin/x"):
            with self.subTest(line=line):
                r, fetched, _ = self.session_start(line)
                self.assertIn("[gauntlet] active - scope: changed vs origin/main;", r.stdout)
                self.assertFalse(fetched)


class DockerPauseShim(unittest.TestCase):
    """gauntlet/hooks/docker_pause_shim.py emulates pause/unpause via SIGSTOP/SIGCONT when CgroupDriver=none."""

    def test_pause_unpause_keepalive_and_upgrade_streams(self):
        import socket
        import threading
        import time

        with tempfile.TemporaryDirectory() as tmp:
            upstream = os.path.join(tmp, "upstream.sock")
            listen = os.path.join(tmp, "shim.sock")
            fake_docker = os.path.join(tmp, "fake-docker")
            target = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
            self.addCleanup(lambda: (target.kill(), target.wait()))

            kit.write(fake_docker, f"#!/bin/sh\nprintf 'PID\\n{target.pid}\\n'\n")
            os.chmod(fake_docker, 0o755)

            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(upstream)
            srv.listen(8)
            self.addCleanup(srv.close)

            def serve_upstream():
                while True:
                    try:
                        conn, _ = srv.accept()
                    except OSError:
                        break
                    with conn:
                        req = b""
                        while b"\r\n\r\n" not in req:
                            chunk = conn.recv(4096)
                            if not chunk:
                                break
                            req += chunk
                        if b"Upgrade: tcp" in req:
                            # read until client half-closes (write_eof), then reply with exec stdout
                            while conn.recv(4096):
                                pass
                            conn.sendall(b"HTTP/1.1 101 UPGRADED\r\nUpgrade: tcp\r\n\r\nEXEC_OK\n")
                        elif req:
                            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK")

            threading.Thread(target=serve_upstream, daemon=True).start()

            shim_src = os.path.join(kit.kit(), "gauntlet", "hooks", "docker_pause_shim.py")
            env = dict(os.environ, DOCKER_UPSTREAM_SOCK=upstream, DOCKER_CLI_BIN=fake_docker)
            shim = subprocess.Popen([sys.executable, "-I", shim_src, listen], env=env)
            self.addCleanup(lambda: (shim.terminate(), shim.wait()))
            for _ in range(50):
                if os.path.exists(listen):
                    break
                time.sleep(0.05)
            self.assertTrue(os.path.exists(listen))

            def call(raw, half_close=False):
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as c:
                    c.connect(listen)
                    c.sendall(raw)
                    if half_close:
                        c.shutdown(socket.SHUT_WR)
                    chunks = []
                    while data := c.recv(4096):
                        chunks.append(data)
                    return b"".join(chunks)

            # 1. Normal HTTP/1.1 keep-alive request gets Connection: close and returns 200 OK
            ping = call(b"GET /v1.44/_ping HTTP/1.1\r\nHost: docker\r\nConnection: keep-alive\r\n\r\n")
            self.assertIn(b"200 OK", ping)
            # 2. Pause freezes the target PID (Linux /proc/<pid>/stat state 'T') and returns 204
            paused = call(b"POST /v1.44/containers/c123/pause HTTP/1.1\r\nHost: docker\r\n\r\n")
            self.assertIn(b"204 No Content", paused)
            if os.path.exists(f"/proc/{target.pid}/stat"):
                for _ in range(20):
                    if ") T " in kit.read(f"/proc/{target.pid}/stat"):
                        break
                    time.sleep(0.05)
                self.assertIn(") T ", kit.read(f"/proc/{target.pid}/stat"))
            # 3. Unpause resumes the target PID via SIGCONT and returns 204
            unpaused = call(b"POST /v1.44/containers/c123/unpause HTTP/1.1\r\nHost: docker\r\n\r\n")
            self.assertIn(b"204 No Content", unpaused)
            if os.path.exists(f"/proc/{target.pid}/stat"):
                for _ in range(20):
                    if ") T " not in kit.read(f"/proc/{target.pid}/stat"):
                        break
                    time.sleep(0.05)
                self.assertNotIn(") T ", kit.read(f"/proc/{target.pid}/stat"))
            # 4. Upgrade: tcp propagates half-close (write_eof) so docker exec receives full output
            upgraded = call(
                b"POST /v1.44/exec/e1/start HTTP/1.1\r\nHost: docker\r\nConnection: Upgrade\r\nUpgrade: tcp\r\n\r\n",
                half_close=True,
            )
            self.assertIn(b"EXEC_OK\n", upgraded)
            # 5. sys.dont_write_bytecode keeps gauntlet/hooks clean even without -B
            bytecode = [d for d, _, _ in os.walk(os.path.join(kit.kit(), "gauntlet")) if d.endswith("__pycache__")]
            self.assertEqual(bytecode, [])

    def test_session_start_auto_starts_shim_when_cgroup_driver_is_none(self):
        import stat

        with tempfile.TemporaryDirectory() as tmp:
            repo = os.path.join(tmp, "repo")
            os.makedirs(repo)
            git(repo, "init", "-q", "-b", "main")
            shutil.copytree(os.path.join(kit.kit(), "gauntlet"), os.path.join(repo, "gauntlet"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "base")
            git(tmp, "clone", "-q", "--bare", repo, "origin.git")
            clone = os.path.join(tmp, "clone")
            git(tmp, "clone", "-q", os.path.join(tmp, "origin.git"), clone)

            bin_dir = os.path.join(tmp, "bin")
            os.makedirs(bin_dir)
            fake_docker = os.path.join(bin_dir, "docker")
            kit.write(fake_docker, "#!/bin/sh\nif [ \"$2\" = \"--format\" ]; then echo none; else echo ok; fi\n")
            os.chmod(fake_docker, 0o755)
            shim_sock = os.path.join(tmp, "auto-pause-shim.sock")
            self.addCleanup(lambda: subprocess.run(["pkill", "-f", shim_sock], stderr=subprocess.DEVNULL))

            env = {k: v for k, v in os.environ.items() if not k.startswith(("GAUNTLET_", "CLAUDE_"))}
            env.update(
                CLAUDE_PROJECT_DIR=clone,
                GAUNTLET_DOCKER="on",
                GAUNTLET_DOCKER_SHIM_SOCK=shim_sock,
                PATH=bin_dir + os.pathsep + env.get("PATH", ""),
            )
            r = subprocess.run(["bash", os.path.join(clone, "gauntlet", "hooks", "session_start.sh")], cwd=clone,
                               input='{"session_id": "s"}', stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(f"docker: up (pause-shim: {shim_sock})", r.stdout)
            self.assertTrue(stat.S_ISSOCK(os.stat(shim_sock).st_mode))


if __name__ == "__main__":
    unittest.main()
