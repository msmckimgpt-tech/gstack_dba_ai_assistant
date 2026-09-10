#!/usr/bin/env python3
"""Add missing global command skills without modifying existing worktrees.

Install after project main branches are updated. Preparation worktrees may also
be supplied for dry runs: the catalog always records durable main repository
paths. Resolution is read-only and never executes the selected command.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import tempfile


OWNER = "ai-delegated-dev-template-global-commands"
CATALOG_NAME = "command-fallbacks.json"


def command_description(path: Path) -> str:
    """Use the same frontmatter reader as project skill installation."""
    spec = importlib.util.spec_from_file_location(
        "codex_environment_install", Path(__file__).resolve().parents[1] / "codex-environment-install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    metadata, _ = module.frontmatter(path.read_text())
    return " ".join(metadata.get("description", "").split())


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(path), *args],
                                   text=True, stderr=subprocess.DEVNULL).strip()


def policy_root(cwd: Path) -> Path:
    candidate = cwd.resolve()
    if (candidate / "repo/AGENTS.md").is_file():
        candidate /= "repo"
    root = Path(git(candidate, "rev-parse", "--show-toplevel")).resolve()
    if not (root / "AGENTS.md").is_file():
        raise ValueError("Current directory is not a registered policy repository")
    return root


def main_root(worktree: Path) -> Path:
    for line in git(worktree, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            return Path(line[9:]).resolve()
    raise ValueError("Could not identify the main worktree")


def is_template(repo: Path) -> bool:
    history = repo / "_template_maintainer/HISTORY.md"
    return (history.is_file() and (repo / "bin/migrations/registry.sh").is_file()
            and re.search(r"^## META-CYCLE-", history.read_text(), re.MULTILINE) is not None)


def allowed(rel: str, main: Path, template_main: Path, dqa_main: Path | None) -> bool:
    namespace = rel.split("/", 1)[0]
    if namespace in ("_local", "_maintainer"):
        return main == template_main
    if namespace == "_dqa":
        return dqa_main is not None and main == dqa_main
    return True


def build_catalog(template: Path, projects: list[Path], dqa_project: Path | None = None) -> dict:
    template_source = policy_root(template)
    if not is_template(template_source):
        raise ValueError("--template must be the actual template base")
    template_main = main_root(template_source)
    dqa_main = main_root(policy_root(dqa_project)) if dqa_project else None
    catalog = {"owner": OWNER, "version": 1, "template_main": str(template_main),
               "dqa_main": str(dqa_main) if dqa_main else None, "commands": {}}
    for source in [template_source, *projects]:
        source = policy_root(source)
        main = main_root(source)
        commands = source / ".codex/commands"
        for path in sorted(commands.rglob("*.md")):
            rel = path.relative_to(commands).as_posix()
            if path.name.lower() == "readme.md" or not allowed(rel, main, template_main, dqa_main):
                continue
            name = rel[:-3].replace("/", "-")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
                raise ValueError(f"Unsupported command name: {rel}")
            item = catalog["commands"].setdefault(name, {"projects": {}})
            description = command_description(path)
            if description:
                item.setdefault("description", description)
            previous = item["projects"].get(str(main))
            if previous and previous != rel:
                raise ValueError(f"Command name collision: {name}")
            item["projects"][str(main)] = rel
    return catalog


def existing_skill_names(home: Path) -> set[str]:
    names = set()
    for root in [home / ".agents/skills", home / ".codex/skills"]:
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            # Starting traversal at each entry includes a linked skill bundle
            # such as gstack without rewriting or following arbitrary commands.
            if not entry.is_dir():
                continue
            for skill in entry.rglob("SKILL.md"):
                names.add(skill.parent.name)
                with skill.open() as stream:
                    text = stream.read(8192)
                match = re.search(r"(?m)^name:\s*[\"']?([A-Za-z0-9_-]+)", text)
                if match:
                    names.add(match.group(1))
    return names


def wrapper(name: str, item: dict, catalog_path: Path, template_main: Path) -> str:
    scope = ("template base only" if name.startswith(("_local-", "_maintainer-")) else
             "mysql_ai_delegated_dev only" if name.startswith("_dqa-") else
             "registered template and consumer projects")
    description = item.get("description") or f"Run the project {name} workflow in {scope}, including older linked worktrees."
    command = " ".join(shlex.quote(x) for x in [
        "python3", str(template_main / "bin/codex-migration/global_commands.py"),
        "resolve", "--catalog", str(catalog_path), "--command", name,
    ])
    return ("---\nname: " + name + "\ndescription: " + json.dumps(description, ensure_ascii=False) + "\n---\n\n"
            "Resolve this command in the current working directory using this read-only helper:\n\n"
            "```bash\n" + command + "\n```\n\n"
            "If resolution fails, report the scope mismatch; do not substitute a command from another project. "
            "Read the returned `runtime_context` for the current Codex compatibility rules, then "
            "read `command_path` and follow it with the current user's arguments as `$ARGUMENTS`. "
            "The resolver reads the current worktree command when present, otherwise this project's "
            "main command. It does not execute either command.\n\n"
            "Keep all policy, task-document and mutation paths anchored to the returned `worktree_root`. "
            "Reading the shared runtime adapter or a main command does not move the task to main. "
            "Resolve source-relative helper files from `command_directory`; never change source code "
            "or task state in another worktree merely because a fallback was read. Read the current "
            "worktree's AGENTS.md and applicable CLAUDE.md domain guidance. Preserve existing changes.\n")


def atomic_write(path: Path, text: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def install(catalog: dict, home: Path, apply: bool = False) -> dict:
    home = home.resolve()
    catalog_path = home / ".codex" / CATALOG_NAME
    if catalog_path.is_symlink():
        raise ValueError("Refusing to replace a symlinked catalog")
    previous_catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {}
    if catalog_path.exists() and previous_catalog.get("owner") != OWNER:
        raise ValueError("An unrelated command catalog already exists")
    existing = existing_skill_names(home)
    result = {"applied": apply, "catalog": str(catalog_path), "created": [], "updated": [], "preserved": []}
    for name, item in sorted(catalog["commands"].items()):
        dest = home / ".agents/skills" / name
        skill = dest / "SKILL.md"
        desired = wrapper(name, item, catalog_path, Path(catalog["template_main"]))
        # Only refresh an exact generated wrapper; custom bodies, extra metadata
        # and symlinks remain owned by the user. The old catalog alone is not
        # proof of ownership, since users can edit an installed skill afterwards.
        if (not dest.is_symlink() and not skill.is_symlink() and skill.is_file()
                and not (home / ".agents").is_symlink()
                and not (home / ".agents/skills").is_symlink()):
            current = skill.read_text()
            old_item = previous_catalog.get("commands", {}).get(name, {})
            # Compare against recorded generated values, never a description
            # read from the candidate itself (which could be a user's edit).
            candidates = [old_item] if old_item else []
            candidates.append({})  # exact pre-description legacy wrapper
            for previous in candidates:
                if current == wrapper(name, previous, catalog_path, Path(catalog["template_main"])):
                    if current != desired:
                        result["updated"].append(name)
                        if apply:
                            with skill.open("w") as stream:
                                stream.write(desired)
                        break
            if name in result["updated"]:
                continue
        if name in existing or os.path.lexists(dest):
            result["preserved"].append(name)
            continue
        result["created"].append(name)
        if apply:
            # Exclusive directory creation prevents a concurrent custom install
            # from being overwritten between the inventory and this write.
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest.mkdir()
            except FileExistsError:
                result["created"].remove(name)
                result["preserved"].append(name)
                continue
            atomic_write(dest / "SKILL.md", wrapper(name, item, catalog_path,
                                                    Path(catalog["template_main"])), 0o644)
    if apply:
        atomic_write(catalog_path, json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", 0o600)
    return result


def resolve(catalog: dict, cwd: Path, name: str) -> dict:
    if catalog.get("owner") != OWNER or catalog.get("version") != 1:
        raise ValueError("Unrecognized command catalog")
    worktree = policy_root(cwd)
    main = main_root(worktree)
    item = catalog.get("commands", {}).get(name, {})
    rel = item.get("projects", {}).get(str(main))
    if not isinstance(rel, str):
        raise ValueError("This command is not registered for the current project")
    parts = PurePosixPath(rel)
    if parts.is_absolute() or ".." in parts.parts or parts.suffix != ".md":
        raise ValueError("Invalid command path in catalog")
    template_main = Path(catalog["template_main"]).resolve()
    dqa_main = Path(catalog["dqa_main"]).resolve() if catalog.get("dqa_main") else None
    if not allowed(rel, main, template_main, dqa_main):
        raise ValueError("This namespace is not available in the current project")
    context = template_main / ".codex/CONTEXT.md"
    if not context.is_file():
        raise ValueError("The shared runtime context is not installed in template main yet")
    for owner in dict.fromkeys([worktree, main]):
        path = owner / ".codex/commands" / rel
        if path.is_file():
            resolved = path.resolve()
            if not resolved.is_relative_to(owner):
                raise ValueError("Command symlink leaves its owning worktree")
            return {"command": name, "worktree_root": str(worktree), "project_main": str(main),
                    "runtime_context": str(context), "command_path": str(path),
                    "command_directory": str(path.parent), "fallback_to_main": owner != worktree}
    raise ValueError("The registered command is missing from both current worktree and main")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    setup = sub.add_parser("install")
    setup.add_argument("--template", type=Path, required=True)
    setup.add_argument("--project", type=Path, action="append", default=[])
    setup.add_argument("--dqa-project", type=Path)
    setup.add_argument("--home", type=Path, default=Path.home())
    setup.add_argument("--apply", action="store_true")
    lookup = sub.add_parser("resolve")
    lookup.add_argument("--catalog", type=Path, required=True)
    lookup.add_argument("--command", required=True)
    lookup.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.action == "install":
            catalog = build_catalog(args.template, args.project, args.dqa_project)
            result = install(catalog, args.home, args.apply)
        else:
            result = resolve(json.loads(args.catalog.read_text()), args.cwd, args.command)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
