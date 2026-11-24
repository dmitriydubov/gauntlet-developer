"""The subagent core of the kit (gauntlet/subagents.md) and the files that must agree with it.

Revision 4.5 put the rules for subagents into one document of the kit and tied it to a role, a tool and a key: the
read-only role `checker` runs a card and returns the report format of section 3, which gauntlet/tools/report_check.py
checks; the roles of a task session carry the thoroughness fields of card 4.5; the key subagents.route of
gauntlet.properties takes the route values of section 5, and the method (section 1.1, item 27) names the same values.
Each of these lives in a file of its own; the tests below check that they agree.
"""
import os
import re
import tempfile
import unittest

import kit
import test_install as install
import test_report_check as report_check

CORE = "gauntlet/subagents.md"
PROPERTIES = "gauntlet/config/gauntlet.properties"
AGENTS = os.path.join(".claude", "agents")
WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
OUTPUT = "Output (exactly this shape)"


def kit_text(rel):
    path = os.path.join(kit.kit(), rel)
    assert os.path.isfile(path), f"the kit has no {rel}"
    return kit.read(path)


def chapters(text):
    """{heading: body} of the '## ' headings of a Markdown text; a '## ' line inside a code fence is not a heading."""
    found, current, fenced = {}, None, False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            current = line[3:]
            found[current] = []
            continue
        if current is not None:
            found[current].append(line)
    return {heading: "\n".join(body) for heading, body in found.items()}


def chapter(rel, heading):
    found = chapters(kit_text(rel)).get(heading)
    assert found is not None, f"{rel} has no section «## {heading}»"
    return found


def core_section(number):
    found = [body for heading, body in chapters(kit_text(CORE)).items() if heading.startswith(f"{number}. ")]
    assert found, f"{CORE} has no section {number}"
    return found[0]


def first_fence(text):
    m = re.search(r"(?ms)^```[^\n]*\n(.*?)^```[ \t]*$", text)
    return m.group(1) if m else None


def report_format():
    block = first_fence(core_section(3))
    assert block, f"section 3 of {CORE} has no report format block"
    return block


def unchecked_reasons(block):
    """The reasons the «Не проверено» line of the report format allows: '- <пункт> — <a (…) | b | c> — <…>'."""
    m = re.search(r"(?m)^- <[^>\n]*> — <([^>\n]*)> — ", block)
    assert m, "the report format has no «Не проверено» line with its reasons"
    return [re.sub(r"\s*\(.*?\)", "", reason).strip() for reason in m.group(1).split("|")]


def front_matter(rel):
    m = re.match(r"---\n(.*?)\n---\n", kit_text(rel), re.S)
    assert m, f"{rel} has no front matter"
    return dict(re.findall(r"(?m)^(\w+):[ \t]*(.*)$", m.group(1)))


def tools_of(rel):
    return sorted(t.strip() for t in front_matter(rel).get("tools", "").split(",") if t.strip())


def role_names():
    directory = os.path.join(kit.kit(), AGENTS)
    return {front_matter(os.path.join(AGENTS, f)).get("name") for f in os.listdir(directory) if f.endswith(".md")}


def key_comment():
    """The comment right above subagents.route in gauntlet.properties."""
    m = re.search(r"(?m)((?:^#.*\n)+)^subagents\.route=", kit_text(PROPERTIES))
    assert m, f"{PROPERTIES} has no key subagents.route with a comment above it"
    return m.group(1)


def property_values():
    """The values the comment of the key lists, in its order: '#   own   = …', '#   codex | agy | … = …'."""
    values = []
    for listed in re.findall(r"(?m)^#\s+(\w+(?:\s*\|\s*\w+)*)\s+=\s", key_comment()):
        values += [value.strip() for value in listed.split("|")]
    assert values, f"the comment of subagents.route in {PROPERTIES} lists no values"
    return values


def core_values():
    """The values section 5 of the core gives the key: the sentence that names `subagents.route`, to its end."""
    m = re.search(r"`subagents\.route`(.*?)\.(?=\s)", core_section(5), re.S)
    assert m, f"section 5 of {CORE} does not name the key subagents.route"
    return re.findall(r"`([a-z]+)`", m.group(1))


def method_item(section, number):
    """Item <number> of the numbered list of section <section> of the method, or None."""
    body = re.search(r"(?ms)^#{2,3} " + re.escape(section) + r"\. .*?(?=^#{1,3} )", kit.read(kit.METHOD))
    assert body, f"the method has no section {section}"
    item = re.search(rf"(?ms)^{number}\. (.*?)(?=^\d+\. |\Z)", body.group(0))
    return item.group(1) if item else None


class CheckerRole(unittest.TestCase):
    """.claude/agents/checker.md: the role a read-only card runs in (core, sections 0.1 and 5)."""

    def test_the_checker_is_named_checker_and_has_exactly_the_reviewer_s_tools(self):
        # the guard judges a subagent by its agent_type, the role's name: "checker" is read-only there, as "reviewer"
        checker, reviewer = os.path.join(AGENTS, "checker.md"), os.path.join(AGENTS, "reviewer.md")
        self.assertEqual(front_matter(checker).get("name"), "checker")
        self.assertEqual(tools_of(checker), tools_of(reviewer))
        self.assertEqual([t for t in tools_of(checker) if t in WRITE_TOOLS], [])

    def test_install_puts_the_checker_where_claude_code_looks(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = install.Project(tmp)
            r = p.install()
            self.assertEqual(r.code, 0, r)
            self.assertIn("added  .claude/agents/checker.md", r.out)
            self.assertEqual(kit.read(p.path(".claude/agents/checker.md")),
                             kit_text(os.path.join(AGENTS, "checker.md")))


class ReportFormat(unittest.TestCase):
    """One report format: section 3 of the core, the checker's output and what report_check.py enforces."""

    def test_the_checker_returns_exactly_the_format_of_section_3(self):
        checker = first_fence(chapter(os.path.join(AGENTS, "checker.md"), OUTPUT))
        self.assertEqual(checker, report_format())

    def test_report_check_enforces_the_sections_and_reasons_of_section_3(self):
        block = report_format()
        headings = re.findall(r"(?m)^## (.+)$", block)        # the first is the header «Карточка …»
        tool = report_check.module()
        self.assertEqual([re.sub(r"\s*\(.*$", "", h) for h in headings[1:]], list(tool.SECTIONS))
        self.assertEqual(unchecked_reasons(block), list(tool.REASONS))


class RoleFormats(unittest.TestCase):
    """The roles of a task session keep their formats and carry the thoroughness fields of card 4.5 of the core."""

    def assert_core_has_card(self, number):
        self.assertRegex(kit_text(CORE), rf"(?m)^### {re.escape(number)}\. ", f"{CORE} has no card {number}")

    def test_a_reviewer_finding_quotes_its_line_and_the_verdict_names_the_files_read(self):
        output = chapter(os.path.join(AGENTS, "reviewer.md"), OUTPUT)
        shape = first_fence(output) or ""
        self.assertIn("VERDICT: APPROVED | CHANGES REQUESTED", shape)
        self.assertRegex(shape, r"(?m)^1\. .* \S+:\d+ «[^»\n]+»")             # the quote right after file:line
        self.assertRegex(shape, r"(?m)^Осмотрено: файлы диффа N из M\b")
        risks = re.search(r"(?m)^Residual risks: (.*)$", shape)
        self.assertIsNotNone(risks, shape)
        for reason in unchecked_reasons(report_format()):                    # the three reasons of the core
            self.assertIn(reason, risks.group(1))
        self.assertIn("APPROVED only with N из N", output)
        self.assert_core_has_card("4.5")

    def test_the_hardener_quotes_the_gate_lines_before_and_after_and_the_mutant_each_test_kills(self):
        final = chapter(os.path.join(AGENTS, "hardener.md"), "Final message")
        self.assertIn("the mutant it kills", final)
        named = re.findall(r"`([\w ]+): …`", final)
        self.assertIn("PIT summary", named)
        # the lines are the ones the gate prints: the main agent compares them with the gate's own output
        tools = os.path.join(kit.kit(), "gauntlet", "tools")
        printed = "".join(kit.read(os.path.join(tools, f)) for f in sorted(os.listdir(tools)) if f.endswith(".java"))
        self.assertEqual([line for line in named if f'"{line}: ' not in printed], [])
        self.assert_core_has_card("4.5")

    def test_a_specifier_assumption_names_a_source_for_the_build_s_version(self):
        final = chapter(os.path.join(AGENTS, "specifier.md"), "Final message")
        self.assertRegex(final, r"card 4\.2 of\s+gauntlet/subagents\.md")
        self.assertIn("verbatim quote", final)
        self.assert_core_has_card("4.2")


class Route(unittest.TestCase):
    """subagents.route: one list of values in the core (section 5), in gauntlet.properties and in the method."""

    def test_section_5_gives_the_key_exactly_the_values_of_its_comment(self):
        self.assertEqual(sorted(core_values()), sorted(property_values()))

    def test_the_key_defaults_to_ask(self):
        self.assertEqual(re.findall(r"(?m)^subagents\.route=(.*)$", kit_text(PROPERTIES)), ["ask"])
        self.assertIn("ask", property_values())

    def test_every_vendor_value_has_its_command_in_the_external_route(self):
        # «**Codex CLI** (`codex`, …):» and right after it the block of the command that runs that CLI
        commands = re.findall(r"(?ms)^\*\*[^*\n]+\*\* \(`([a-z]+)`[^\n]*\n```[^\n]*\n(.*?)^```", core_section(5))
        self.assertEqual(sorted(v for v, _ in commands), sorted(set(property_values()) - {"ask", "own"}))
        for value, command in commands:
            self.assertRegex(command, rf"(?<![\w-]){value}(?![\w-])", f"the command of `{value}` does not run it")

    def test_the_comment_of_the_key_points_at_the_route_section_of_the_core(self):
        # the comment names the section by title and by number; both must be the one section that gives the values
        comment = key_comment()
        titles = re.findall(r'gauntlet/subagents\.md, "([^"]+)"', comment)
        numbers = re.findall(r"gauntlet/subagents\.md, section (\d+)", comment)
        self.assertTrue(titles or numbers, f"the comment of subagents.route does not point at {CORE}")
        sections = {h.split(". ", 1)[0]: (h.split(". ", 1)[1], body)
                    for h, body in chapters(kit_text(CORE)).items() if re.match(r"\d+\. ", h)}
        route = [n for n, (_, body) in sections.items() if "`subagents.route`" in body]
        self.assertEqual(len(route), 1, f"sections of {CORE} that give the key its values: {route}")
        for title in titles:
            self.assertEqual([n for n, (t, _) in sections.items() if t.startswith(title)], route, title)
        for number in numbers:
            self.assertEqual([number], route)

    def test_item_27_of_the_method_names_exactly_the_route_values_of_the_kit(self):
        values = sorted(property_values())
        item = method_item("1.1", 27)
        if item is None:
            self.skipTest("the method has no item 27 in section 1.1 (the subagent route of revision 4.5)")
        self.assertIn("`subagents.route`", item, "item 27 of section 1.1 of the method does not name the key")
        # the values are what item 27 puts in backticks as a bare lowercase word, a role name (`checker`) aside
        named = sorted(set(re.findall(r"`([a-z]+)`", item)) - role_names())
        self.assertEqual(named, values, "the route values item 27 of the method names are not the key's")


if __name__ == "__main__":
    unittest.main()
