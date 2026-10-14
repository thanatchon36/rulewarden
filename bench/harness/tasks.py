"""Benchmark task model: load bench/tasks/<id>/task.yaml and materialise its rule set.

task.yaml: {id, language, rules: [library ids], extra_rules: [full rule bodies]}.
The task directory also holds TASK.md (the prompt), repo/ (the starting workspace)
and hidden/ (tests copied in only for scoring).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BENCH = Path(__file__).resolve().parents[1]
TASKS = BENCH / "tasks"
LIBRARY = BENCH / "ruleset" / "library.yaml"


@dataclass(frozen=True)
class Task:
    id: str
    dir: Path
    language: str
    prompt: str
    rules: list[dict[str, Any]]

    @property
    def repo(self) -> Path:
        return self.dir / "repo"

    @property
    def hidden(self) -> Path:
        return self.dir / "hidden"

    def rules_yaml(self) -> str:
        return yaml.safe_dump({"version": 1, "rules": self.rules}, sort_keys=False, width=120)

    def rules_markdown(self) -> str:
        lines = ["## Rules", ""]
        lines += [f"- {r['title']}: {r['message']}" for r in self.rules]
        return "\n".join(lines) + "\n"


def library() -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(LIBRARY.read_text(encoding="utf-8"))
    return {r["id"]: r for r in data["rules"]}


def load(task_id: str) -> Task:
    d = TASKS / task_id
    spec = yaml.safe_load((d / "task.yaml").read_text(encoding="utf-8"))
    lib = library()
    rules = [lib[i] for i in spec.get("rules", [])] + list(spec.get("extra_rules", []))
    if not 5 <= len(rules) <= 10:
        raise ValueError(f"{task_id}: {len(rules)} rules; a task needs 5-10")
    return Task(
        id=spec["id"],
        dir=d,
        language=spec["language"],
        prompt=(d / "TASK.md").read_text(encoding="utf-8"),
        rules=rules,
    )


def all_ids() -> list[str]:
    return sorted(p.name for p in TASKS.iterdir() if (p / "task.yaml").is_file())
