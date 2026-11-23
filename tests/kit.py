"""Shared helpers of the kit regression suite (see tests/README.md).

tests/run.py unpacks gauntlet-kit-bundle.md, compiles the single-file Java tools and exports:
  GAUNTLET_REPO     the repository root (the documents)
  GAUNTLET_KIT      the unpacked kit (contains gauntlet/, .claude/, .github/, CLAUDE.md)
  GAUNTLET_CLASSES  the compiled tools (CrapGate, DryGate, GherkinMutator, IntegrityCheck, PitSummary)
A test module can also be run on its own: the helpers below then unpack and compile on first use.
"""
import atexit
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.environ.get("GAUNTLET_REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(REPO, "gauntlet-kit-bundle.md")
METHOD = os.path.join(REPO, "gauntlet-method-universal.md")
TOOLS = ("CrapGate", "DryGate", "GherkinMutator", "IntegrityCheck", "PitSummary")
_state = {}


def read(path, encoding="utf-8"):
    with open(path, encoding=encoding, newline="") as f:
        return f.read()


def write(path, text, encoding="utf-8"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = text if isinstance(text, bytes) else text.encode(encoding)
    with open(path, "wb") as f:
        f.write(data)
    return path


def bundle_extractor(bundle_text):
    """The unpack script published in the bundle header - the suite unpacks with exactly what a user gets."""
    m = re.search(r"^## Как распаковать.*?^```python\n(.*?)^```$", bundle_text, re.S | re.M)
    assert m, "the bundle header has no unpack script"
    return m.group(1)


def unpack(bundle_path, target):
    os.makedirs(target, exist_ok=True)
    script = os.path.join(target, ".extract_bundle.py")
    write(script, bundle_extractor(read(bundle_path)))
    subprocess.run([sys.executable, "-I", script, os.path.abspath(bundle_path)], cwd=target, check=True,
                   stdout=subprocess.DEVNULL)
    os.remove(script)
    return target


def compile_tools(kit, classes):
    os.makedirs(classes, exist_ok=True)
    sources = [os.path.join(kit, "gauntlet", "tools", t + ".java") for t in TOOLS]
    r = subprocess.run(["javac", "-nowarn", "-d", classes, *sources], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, env=java_env())
    assert r.returncode == 0, "javac failed:\n" + r.stdout
    return classes


def java_env():
    env = dict(os.environ)
    env.setdefault("LC_ALL", "C.UTF-8")     # non-ASCII class and file names need a UTF-8 file-name encoding
    return env


def _prepare():
    if "kit" not in _state:
        kit, classes = os.environ.get("GAUNTLET_KIT"), os.environ.get("GAUNTLET_CLASSES")
        if not kit:
            root = tempfile.mkdtemp(prefix="gauntlet-kit-tests-")
            atexit.register(shutil.rmtree, root, ignore_errors=True)
            kit = unpack(BUNDLE, os.path.join(root, "kit"))
        if not classes:
            classes = compile_tools(kit, tempfile.mkdtemp(prefix="gauntlet-kit-classes-"))
            atexit.register(shutil.rmtree, classes, ignore_errors=True)
        _state["kit"], _state["classes"] = kit, classes
    return _state["kit"], _state["classes"]


def kit():
    return _prepare()[0]


def classes():
    return _prepare()[1]


class Result:
    def __init__(self, completed):
        self.code = completed.returncode
        # the JVM announces JAVA_TOOL_OPTIONS on stderr in some environments: not tool output
        self.out = "\n".join(l for l in completed.stdout.splitlines() if not l.startswith("Picked up "))

    def __repr__(self):
        return f"exit {self.code}\n{self.out}"


def tool(name, *args, cwd=None):
    """Runs a compiled single-file tool the way gauntlet.gradle does (arguments only, no stdin)."""
    r = subprocess.run(["java", "-cp", classes(), name, *[str(a) for a in args]], cwd=cwd, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, encoding="utf-8", env=java_env())
    return Result(r)


def run(cmd, cwd=None, env=None, input=None):
    r = subprocess.run(cmd, cwd=cwd, env=env, input=input, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return Result(r)


def copy_kit(target):
    """A project-shaped copy of the kit as it is before install.sh: roles, settings and workflow under gauntlet/."""
    src = kit()
    shutil.copytree(os.path.join(src, "gauntlet"), os.path.join(target, "gauntlet"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    os.makedirs(os.path.join(target, "gauntlet", "claude"))
    shutil.copy(os.path.join(src, ".claude", "settings.json"), os.path.join(target, "gauntlet", "claude", "settings.json"))
    shutil.copytree(os.path.join(src, ".claude", "agents"), os.path.join(target, "gauntlet", "claude", "agents"))
    os.makedirs(os.path.join(target, "gauntlet", "ci"))
    shutil.copy(os.path.join(src, ".github", "workflows", "gauntlet.yml"), os.path.join(target, "gauntlet", "ci", "gauntlet.yml"))
    return target


def set_property(project, key, value, module=None):
    """Sets key=value in gauntlet/config/gauntlet.properties (or in the module's overlay)."""
    rel = "gauntlet/config/" + (module + "/" if module else "") + "gauntlet.properties"
    path = os.path.join(project, rel)
    text = read(path) if os.path.exists(path) else ""
    pattern = re.compile(r"(?m)^" + re.escape(key) + r"=.*$")
    text = pattern.sub(lambda m: f"{key}={value}", text) if pattern.search(text) else text + f"{key}={value}\n"
    write(path, text)
