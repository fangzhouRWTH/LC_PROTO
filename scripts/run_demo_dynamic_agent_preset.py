#!/usr/bin/env python3
"""Run a generated people+vehicle dynamic-agent preset JSON."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNNER = REPO_ROOT / "scripts" / "run_demo_tencent_dynamic_agents.sh"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a generated dynamic agent preset.")
    parser.add_argument("--preset-json", type=Path, required=True)
    parser.add_argument(
        "--runner",
        type=Path,
        default=DEFAULT_RUNNER,
        help=f"Runtime wrapper to execute. Default: {DEFAULT_RUNNER}",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Extra arguments passed after -- to the runtime wrapper.",
    )
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    with path.expanduser().open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Preset JSON must be an object: {path}")
    return value


def _resolve_path(value: str, preset_path: Path) -> str:
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    repo_candidate = REPO_ROOT / path
    if repo_candidate.exists() or not (preset_path.parent / path).exists():
        return str(repo_candidate)
    return str((preset_path.parent / path).resolve())


def _build_env(preset: dict[str, Any], preset_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    raw_env = preset.get("environment") if isinstance(preset.get("environment"), dict) else {}
    for key, value in raw_env.items():
        if value is None:
            continue
        env[str(key)] = str(value)

    scene_usd = preset.get("scene_usd")
    if isinstance(scene_usd, str) and scene_usd:
        env["SCENE_USD"] = _resolve_path(scene_usd, preset_path)

    dynamic_routes = preset.get("dynamic_routes_json")
    if isinstance(dynamic_routes, str) and dynamic_routes:
        env["DYNAMIC_ROUTES_JSON"] = _resolve_path(dynamic_routes, preset_path)
    else:
        placement_plan = preset.get("placement_plan_json")
        if isinstance(placement_plan, str) and placement_plan:
            env["DEMO_PEOPLE_PLACEMENT_PLAN"] = _resolve_path(placement_plan, preset_path)
            env["DEMO_PEOPLE_USE_STATIC_PLAN"] = "true"

    scenario = preset.get("scenario")
    if isinstance(scenario, str) and scenario:
        env["DEMO_PEOPLE_SCENARIO"] = scenario

    return env


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    preset_path = args.preset_json.expanduser().resolve()
    preset = _load_json(preset_path)
    env = _build_env(preset, preset_path)
    runner = args.runner.expanduser().resolve()
    if not runner.exists():
        raise FileNotFoundError(runner)
    extra_args = list(args.args)
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]
    print(f"[INFO] Running preset: {preset_path}", flush=True)
    print(f"[INFO] Scene: {env.get('SCENE_USD', '')}", flush=True)
    print(f"[INFO] Dynamic routes: {env.get('DYNAMIC_ROUTES_JSON', '')}", flush=True)
    print(f"[INFO] Scenario: {env.get('DEMO_PEOPLE_SCENARIO', '')}", flush=True)
    return subprocess.call([str(runner), *extra_args], cwd=REPO_ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
