#!/usr/bin/env python3
"""Structural checks a plugin has to pass before it will install.

Run in CI so a broken manifest is caught here rather than in the install
dialog. Every rule below corresponds to a real failure someone has shipped.
"""

import json
import os
import re
import sys

import yaml

DESC_LIMIT = 1024      # enforced by the plugin loader
BODY_WORD_LIMIT = 3000  # progressive-disclosure guideline

fail = []


def check(cond, msg):
    if not cond:
        fail.append(msg)


manifest = json.load(open(".claude-plugin/plugin.json"))
check(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", manifest.get("name", "")),
      f"plugin name is not kebab-case: {manifest.get('name')!r}")
check(bool(manifest.get("description")), "plugin.json has no description")
check(re.fullmatch(r"\d+\.\d+\.\d+", manifest.get("version", "")),
      f"version is not semver: {manifest.get('version')!r}")

for skill in sorted(os.listdir("skills")):
    path = f"skills/{skill}/SKILL.md"
    if not os.path.exists(path):
        fail.append(f"{skill}: no SKILL.md")
        continue
    text = open(path).read()
    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not front:
        fail.append(f"{skill}: no YAML frontmatter")
        continue
    meta = yaml.safe_load(front.group(1))
    desc = (meta.get("description") or "").strip()
    body = len(re.sub(r"^---.*?---", "", text, flags=re.S).split())

    check(meta.get("name") == skill,
          f"{skill}: frontmatter name is {meta.get('name')!r}")
    check(desc, f"{skill}: no description")
    check(len(desc) <= DESC_LIMIT,
          f"{skill}: description is {len(desc)} chars, limit {DESC_LIMIT}")
    check(body <= BODY_WORD_LIMIT,
          f"{skill}: body is {body} words, guideline {BODY_WORD_LIMIT}")

# Every intra-plugin path reference has to resolve, or a skill sends the model
# looking for a file that is not there.
for dirpath, _, files in os.walk("."):
    if "/." in dirpath or dirpath.startswith("./."):
        continue
    for name in files:
        if not name.endswith(".md"):
            continue
        full = os.path.join(dirpath, name)
        text = open(full, errors="replace").read()
        for ref in re.findall(r"`\$\{CLAUDE_PLUGIN_ROOT\}/([^`\s]+?)`", text):
            check(os.path.exists(ref.split()[0]), f"{full} -> missing {ref}")
        for ref in re.findall(r"`(references/[a-z0-9-]+\.md)`", text):
            check(os.path.exists(os.path.join(dirpath, ref)),
                  f"{full} -> missing {ref}")

if fail:
    print("Plugin validation failed:")
    for f in fail:
        print(f"  {f}")
    sys.exit(1)
print(f"Plugin valid: {manifest['name']} {manifest['version']}, "
      f"{len(os.listdir('skills'))} skills")
