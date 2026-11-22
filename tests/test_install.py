"""gauntlet/install.sh: fresh install, merge into existing Claude Code settings, upgrade, and what stays the user's."""
import json
import os
import shutil
import tempfile
import unittest

import kit

P = '"$CLAUDE_PROJECT_DIR/gauntlet/hooks/'          # how the kit itself spells a hook script
GUARD = f'python3 {P}guard.py"'
FAST = f'python3 {P}stop_gate.py" --task gauntletFast --max-attempts 3 --timeout 1700'
MUTATION = f'python3 {P}stop_gate.py" --task mutationGate --max-attempts 2 --timeout 3300'


def hook(command, **fields):
    return dict({"type": "command", "command": command}, **fields)


class Project:

    def __init__(self, tmp, modules="", build=True):
        self.root = kit.copy_kit(os.path.join(tmp, "project"))
        kit.set_property(self.root, "module", modules)
        if build:
            for module in [m for m in modules.split(",") if m] or ["."]:
                kit.write(os.path.join(self.root, module, "build.gradle"), 'apply from: "gauntlet/gauntlet.gradle"\n')

    def path(self, rel):
        return os.path.join(self.root, rel)

    def settings(self, value=None):
        if value is not None:
            kit.write(self.path(".claude/settings.json"), value if isinstance(value, str) else json.dumps(value, indent=2))
        return json.loads(kit.read(self.path(".claude/settings.json")))

    def install(self):
        return kit.run(["bash", "gauntlet/install.sh"], cwd=self.root)

    def restore_sources(self):
        """A later kit version arrives the same way the first one did: gauntlet/claude and gauntlet/ci again."""
        shutil.rmtree(self.path("gauntlet"))
        kit.copy_kit(self.root + ".next")
        shutil.move(self.root + ".next/gauntlet", self.path("gauntlet"))

    def hooks(self, event):
        return [(g.get("matcher"), h["command"], h.get("timeout"))
                for g in self.settings()["hooks"].get(event, []) for h in g.get("hooks", [])]

    def commands(self, event):
        return [command for _, command, _ in self.hooks(event)]


class InstallCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def project(self, **kw):
        return Project(self.tmp.name, **kw)


class FreshInstall(InstallCase):

    def test_everything_lands_in_place(self):
        p = self.project()
        r = p.install()
        self.assertEqual(r.code, 0, r)
        s = p.settings()
        self.assertIs(s["disableAllHooks"], False)
        self.assertEqual(p.hooks("PreToolUse"), [("Edit|Write|MultiEdit|NotebookEdit|Bash", GUARD, None)])
        self.assertEqual(p.hooks("Stop"), [(None, FAST, 1800)])
        self.assertEqual(p.hooks("SubagentStop"), [("^hardener$", MUTATION, 7200)])
        self.assertIn("Bash(gh pr merge:*)", s["permissions"]["deny"])
        for rel in (".claude/agents/hardener.md", ".claude/agents/reviewer.md", ".claude/agents/specifier.md",
                    ".github/workflows/gauntlet.yml"):
            self.assertTrue(os.path.isfile(p.path(rel)), rel)
        self.assertEqual(kit.read(p.path("CLAUDE.md")), "@gauntlet/CLAUDE.md\n")
        self.assertFalse(os.path.exists(p.path("gauntlet/claude")))
        self.assertFalse(os.path.exists(p.path("gauntlet/ci")))

    def test_outer_timeouts_grow_with_the_number_of_modules(self):
        expected = {"core": (1800, 7200), "core,adapter": (3500, 7200), "core,adapter,web": (5200, 10500)}
        for modules, (stop, subagent) in expected.items():
            with self.subTest(modules=modules):
                with tempfile.TemporaryDirectory() as tmp:
                    p = Project(tmp, modules=modules)
                    self.assertEqual(p.install().code, 0)
                    self.assertEqual(p.hooks("Stop")[0][2], stop)
                    self.assertEqual(p.hooks("SubagentStop")[0][2], subagent)

    def test_not_a_gradle_project_is_refused(self):
        p = self.project(build=False)
        r = p.install()
        self.assertEqual(r.code, 1, r)
        self.assertFalse(os.path.exists(p.path(".claude")))

    def test_broken_settings_are_refused_before_anything_changes(self):
        p = self.project()
        kit.write(p.path(".claude/settings.json"), "{ not json")
        r = p.install()
        self.assertEqual(r.code, 1, r)
        self.assertEqual(kit.read(p.path(".claude/settings.json")), "{ not json")
        self.assertTrue(os.path.isdir(p.path("gauntlet/claude")))
        self.assertFalse(os.path.exists(p.path(".github")))

    def test_claude_md_import_is_appended_once(self):
        p = self.project()
        kit.write(p.path("CLAUDE.md"), "# service\n")
        self.assertEqual(p.install().code, 0)
        self.assertEqual(kit.read(p.path("CLAUDE.md")), "# service\n\n@gauntlet/CLAUDE.md\n")
        p.restore_sources()
        self.assertEqual(p.install().code, 0)
        self.assertEqual(kit.read(p.path("CLAUDE.md")).count("@gauntlet/CLAUDE.md"), 1)


class Upgrade(InstallCase):

    def test_installed_hooks_are_refreshed_in_place(self):
        # what revision 4.2 installed: the SubagentStop budget was 3600 s
        p = self.project()
        p.settings({"hooks": {
            "PreToolUse": [{"matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash", "hooks": [hook(GUARD)]}],
            "Stop": [{"hooks": [hook(f'python3 {P}stop_gate.py" --task gauntletFast --max-attempts 3 --timeout 1500',
                                     timeout=1600)]}],
            "SubagentStop": [{"matcher": "^hardener$", "hooks": [hook(MUTATION, timeout=3600)]}]}})
        self.assertEqual(p.install().code, 0)
        self.assertEqual(p.hooks("PreToolUse"), [("Edit|Write|MultiEdit|NotebookEdit|Bash", GUARD, None)])
        self.assertEqual(p.hooks("Stop"), [(None, FAST, 1800)])
        self.assertEqual(p.hooks("SubagentStop"), [("^hardener$", MUTATION, 7200)])

    def test_second_run_changes_nothing(self):
        p = self.project(modules="core,adapter")
        self.assertEqual(p.install().code, 0)
        first = kit.read(p.path(".claude/settings.json"))
        p.restore_sources()
        kit.set_property(p.root, "module", "core,adapter")
        self.assertEqual(p.install().code, 0)
        self.assertEqual(kit.read(p.path(".claude/settings.json")), first)

    def test_relative_spelling_of_a_managed_hook_is_not_duplicated(self):
        p = self.project()
        p.settings({"hooks": {"SubagentStop": [{"matcher": "^hardener$", "hooks": [
            hook("python3 ./gauntlet/hooks/stop_gate.py --task mutationGate --timeout 3300", timeout=3600)]}]}})
        self.assertEqual(p.install().code, 0)
        self.assertEqual(p.hooks("SubagentStop"), [("^hardener$", MUTATION, 7200)])

    def test_permissions_are_united_and_the_user_s_rules_stay(self):
        p = self.project()
        p.settings({"permissions": {"allow": ["Bash(npm test:*)", "Bash(git:*)"], "deny": ["Bash(curl:*)"]}})
        self.assertEqual(p.install().code, 0)
        perms = p.settings()["permissions"]
        self.assertEqual(perms["allow"][:2], ["Bash(npm test:*)", "Bash(git:*)"])
        self.assertEqual(perms["allow"].count("Bash(git:*)"), 1)
        self.assertIn("Bash(curl:*)", perms["deny"])
        self.assertIn("Bash(git push --force:*)", perms["deny"])

    def test_changed_role_and_workflow_arrive_as_copies_to_merge(self):
        p = self.project()
        kit.write(p.path(".claude/agents/reviewer.md"), "my reviewer\n")
        kit.write(p.path(".github/workflows/gauntlet.yml"), "name: mine\n")
        shutil.copy(p.path("gauntlet/claude/agents/hardener.md"), p.path(".claude/agents/hardener.md"))
        r = p.install()
        self.assertEqual(r.code, 0, r)
        self.assertEqual(kit.read(p.path(".claude/agents/reviewer.md")), "my reviewer\n")
        self.assertTrue(os.path.isfile(p.path(".claude/agents/reviewer.md.gauntlet.new")))
        self.assertFalse(os.path.exists(p.path(".claude/agents/hardener.md.gauntlet.new")))
        self.assertEqual(kit.read(p.path(".github/workflows/gauntlet.yml")), "name: mine\n")
        self.assertTrue(os.path.isfile(p.path(".github/workflows/gauntlet.yml.gauntlet.new")))


class UserHooksStayUntouched(InstallCase):

    def assert_kept(self, event, user_commands, managed, matcher=None):
        p = self.project()
        group = {"hooks": [hook(c) for c in user_commands]}
        if matcher:
            group["matcher"] = matcher
        p.settings({"hooks": {event: [group]}})
        r = p.install()
        self.assertEqual(r.code, 0, r)
        commands = p.commands(event)
        for c in user_commands:
            self.assertIn(c, commands)
        self.assertEqual(commands.count(managed), 1, commands)
        self.assertEqual(len(commands), len(user_commands) + 1, commands)
        return p

    def test_commands_that_only_mention_a_hook_script(self):
        self.assert_kept("PreToolUse", [
            f'sha256sum {P}guard.py"',
            f"python3 -c 'print(open(\"gauntlet/hooks/guard.py\").read())'",
            'python3 "$CLAUDE_PROJECT_DIR/legacy-gauntlet/hooks/guard.py"',
            'python3 "$CLAUDE_PROJECT_DIR/tools/gauntlet/hooks/guard.py"'], GUARD)

    def test_compound_commands_keep_their_second_half(self):
        self.assert_kept("PreToolUse", [
            f"{GUARD} && ./tools/record-reviewed-files",
            f"{GUARD}\n./tools/record-reviewed-files",
            f"{GUARD} | tee /tmp/guard.log",
            f"{GUARD} > /tmp/guard.log"], GUARD)

    def test_stop_gate_followed_by_another_command(self):
        self.assert_kept("SubagentStop", [f"{MUTATION}; ./tools/audit", f"{MUTATION} --profile ci"], MUTATION,
                         matcher="^hardener$")

    def test_operator_glued_to_an_option_value_is_a_compound_command(self):
        # shlex reads `3300&&./tools/audit` as ONE word: it is no timeout, and the user's auditor must survive
        self.assert_kept("SubagentStop", [f"{MUTATION}&&./tools/audit", f"{MUTATION}&", f"{MUTATION}>/tmp/gate.log",
                                          f"{MUTATION}2>&1"], MUTATION, matcher="^hardener$")

    def test_second_stop_gate_hook_with_another_task(self):
        # one script, several purposes: the user's own tasks are not the kit's gauntletFast hook
        integration = f'python3 {P}stop_gate.py" --task integrationTest --timeout 1200'
        contract = f'python3 {P}stop_gate.py" --task=contractTest --timeout=900'
        p = self.project()
        p.settings({"hooks": {"Stop": [{"hooks": [
            hook(f'python3 {P}stop_gate.py" --task gauntletFast --timeout 1500', timeout=1600),
            hook(integration, timeout=1300), hook(contract, timeout=1000)]}]}})
        self.assertEqual(p.install().code, 0)
        self.assertEqual(p.hooks("Stop"), [(None, FAST, 1800), (None, integration, 1300), (None, contract, 1000)])

    def test_managed_hook_leaves_a_mixed_group_with_a_broader_matcher(self):
        auditor = "./tools/audit-subagent"
        p = self.project()
        p.settings({"hooks": {"SubagentStop": [{"matcher": "^(hardener|reviewer)$",
                                                 "hooks": [hook(auditor), hook(MUTATION, timeout=3600)]}]}})
        self.assertEqual(p.install().code, 0)
        self.assertEqual(p.hooks("SubagentStop"), [("^(hardener|reviewer)$", auditor, None), ("^hardener$", MUTATION, 7200)])


if __name__ == "__main__":
    unittest.main()
