"""Подсказки из README образа: порты, тома, переменные."""

from __future__ import annotations

import re
from typing import Any

import yaml

FENCE = re.compile(r"```(?:ya?ml)?\s*\n(.*?)```", re.S)
BLOCK = re.compile(r"(?ms)^\s*(ports|volumes):\s*\n((?:[ \t]*-[^\n]*\n?)+)")
ITEM = re.compile(r"-\s*(.+)")
RUN = re.compile(r"docker\s+run\b[^\n]*")


def normalize_port(value: str) -> str:
    text = value.strip().strip("'\"")
    body, _, kind = text.partition("/")
    parts = body.split(":")
    if len(parts) >= 3:
        body = f"{parts[-2]}:{parts[-1]}"
    return f"{body}/{kind or 'tcp'}"


def normalize_volume(value: str) -> str:
    text = value.strip().strip("'\"")
    source, sep, target = text.partition(":")
    if not sep:
        return text
    if source.startswith("./"):
        source = source[2:]
    return f"{source}:{target}"


def _from_compose(data: dict) -> tuple[list[str], list[str], dict[str, str]]:
    ports: list[str] = []
    volumes: list[str] = []
    env: dict[str, str] = {}
    for service in (data.get("services") or {}).values():
        if not isinstance(service, dict):
            continue
        for item in service.get("ports") or []:
            ports.append(str(item))
        for item in service.get("volumes") or []:
            volumes.append(str(item))
        environment = service.get("environment")
        if isinstance(environment, dict):
            env.update({str(key): str(value or "") for key, value in environment.items()})
        elif isinstance(environment, list):
            for item in environment:
                key, sep, value = str(item).partition("=")
                if sep:
                    env[key] = value
    return ports, volumes, env


def _from_run(line: str) -> tuple[list[str], list[str], dict[str, str]]:
    ports = re.findall(r"-p\s+([^\s\\]+)", line)
    volumes = re.findall(r"-v\s+([^\s\\]+)", line)
    env = {}
    for item in re.findall(r"-e\s+([A-Za-z_][A-Za-z0-9_]*=[^\s\\]*)", line):
        key, _, value = item.partition("=")
        env[key] = value
    return ports, volumes, env


def _block_items(text: str, kind: str) -> list[str]:
    items = []
    for match in BLOCK.finditer(text):
        if match.group(1) != kind:
            continue
        for line in match.group(2).splitlines():
            found = ITEM.search(line)
            if found:
                items.append(found.group(1).strip())
    return items


def extract_hints(markdown: str) -> dict[str, Any]:
    text = markdown or ""
    ports: list[str] = []
    volumes: list[str] = []
    env: dict[str, str] = {}

    for block in FENCE.findall(text):
        if "services:" in block:
            try:
                data = yaml.safe_load(block)
            except yaml.YAMLError:
                continue
            if isinstance(data, dict):
                found_ports, found_volumes, found_env = _from_compose(data)
                ports.extend(found_ports)
                volumes.extend(found_volumes)
                env.update(found_env)
        elif "docker run" in block:
            found_ports, found_volumes, found_env = _from_run(block)
            ports.extend(found_ports)
            volumes.extend(found_volumes)
            env.update(found_env)

    # блоки ports:/volumes: вне ```-ограждений (например, README Elestio)
    ports.extend(_block_items(text, "ports"))
    volumes.extend(_block_items(text, "volumes"))
    found_ports, found_volumes, found_env = _from_run(text)
    ports.extend(found_ports)
    volumes.extend(found_volumes)
    env.update(found_env)

    def unique(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

    return {
        "ports": unique([normalize_port(item) for item in ports])[:10],
        "volumes": unique([normalize_volume(item) for item in volumes])[:10],
        "env": dict(list(env.items())[:10]),
    }
