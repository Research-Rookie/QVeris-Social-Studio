"""Shared QVeris helpers for finance data pipelines."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


QVERIS_BASE_URL = os.environ.get("QVERIS_API_BASE_URL", "https://qveris.ai/api/v1")
QVERIS_API_KEY = os.environ.get("QVERIS_API_KEY")
QVERIS_MAX_EXPECTED_CREDITS = float(os.environ.get("QVERIS_MAX_EXPECTED_CREDITS", "30"))


def headers() -> dict[str, str]:
    if not QVERIS_API_KEY:
        raise RuntimeError("QVERIS_API_KEY is not set")
    return {
        "Authorization": f"Bearer {QVERIS_API_KEY}",
        "Content-Type": "application/json",
    }


def post_json(path: str, payload: dict[str, Any], query: dict[str, Any] | None = None) -> dict[str, Any]:
    suffix = f"?{urlencode(query)}" if query else ""
    request = Request(
        f"{QVERIS_BASE_URL}{path}{suffix}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers(),
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"QVeris API error {error.code} for {path}: {details}") from error


def expected_credits(tool: dict[str, Any]) -> float:
    billing_rule = tool.get("billing_rule") or {}
    price = billing_rule.get("price") or {}
    candidates = [
        billing_rule.get("amount_credits"),
        billing_rule.get("amount"),
        price.get("amount_credits") if isinstance(price, dict) else None,
        tool.get("cost"),
    ]
    for candidate in candidates:
        if candidate not in (None, ""):
            try:
                return float(candidate)
            except (TypeError, ValueError):
                pass
    text = str(tool.get("expected_cost") or "")
    for token in text.replace(",", " ").split():
        try:
            return float(token)
        except ValueError:
            pass
    return 0.0


def search_tools(query: str, session_id: str, limit: int = 8) -> tuple[str, list[dict[str, Any]]]:
    data = post_json(
        "/search",
        {
            "query": query,
            "limit": limit,
            "session_id": session_id,
        },
    )
    search_id = data.get("search_id") or ""
    results = data.get("results") or []
    if not isinstance(results, list):
        raise RuntimeError(f"Unexpected QVeris search response: {data}")
    return search_id, results


def fill_default_parameters(tool: dict[str, Any], explicit: dict[str, Any] | None = None) -> dict[str, Any]:
    explicit = explicit or {}
    parameters: dict[str, Any] = {}
    for param in tool.get("params") or []:
        name = str(param.get("name") or "")
        if not name:
            continue
        lowered = name.lower()
        if name in explicit:
            parameters[name] = explicit[name]
        elif lowered in explicit:
            parameters[name] = explicit[lowered]
        elif lowered in {"symbol", "ticker", "stock_symbol", "stock"} and "symbol" in explicit:
            parameters[name] = explicit["symbol"]
        elif lowered in {"query", "q", "keyword"} and "query" in explicit:
            parameters[name] = explicit["query"]
        elif lowered in {"limit", "count", "top", "size"}:
            parameters[name] = explicit.get("limit", 20)
        elif lowered in {"market", "country", "region", "exchange"}:
            parameters[name] = explicit.get("market", "US")
        elif bool(param.get("required")):
            type_name = str(param.get("type") or "").lower()
            if "number" in type_name or "integer" in type_name:
                parameters[name] = explicit.get("limit", 20)
            else:
                parameters[name] = explicit.get("query", "US stocks")
    return parameters


def choose_tool(
    query: str,
    session_id: str,
    configured_tool_id: str = "",
) -> tuple[str, str, dict[str, Any]]:
    if configured_tool_id:
        return "", configured_tool_id, {"tool_id": configured_tool_id, "params": []}

    search_id, results = search_tools(query, session_id)
    candidates: list[tuple[float, dict[str, Any]]] = []
    for result in results:
        tool_id = result.get("tool_id")
        if not tool_id:
            continue
        cost = expected_credits(result)
        if cost and cost > QVERIS_MAX_EXPECTED_CREDITS:
            continue
        candidates.append((cost, result))

    if not candidates:
        raise RuntimeError(f"No QVeris finance capability found for query: {query}")

    candidates.sort(key=lambda item: item[0])
    selected = candidates[0][1]
    print(f"QVeris tool: {selected.get('name')} ({selected['tool_id']})")
    return search_id, selected["tool_id"], selected


def execute_tool(
    tool_id: str,
    session_id: str,
    parameters: dict[str, Any],
    search_id: str = "",
    max_response_size: int = 32768,
) -> dict[str, Any]:
    data = post_json(
        "/tools/execute",
        {
            "search_id": search_id,
            "session_id": session_id,
            "parameters": parameters,
            "max_response_size": max_response_size,
        },
        {"tool_id": tool_id},
    )
    if not data.get("success", False):
        raise RuntimeError(data.get("error_message") or f"QVeris execution failed for {tool_id}")
    return data.get("result") or {}


def execute_best_tool(
    query: str,
    session_id: str,
    explicit_parameters: dict[str, Any] | None = None,
    configured_tool_id: str = "",
    max_response_size: int = 32768,
) -> dict[str, Any]:
    search_id, tool_id, tool = choose_tool(query, session_id, configured_tool_id)
    if configured_tool_id:
        parameters = explicit_parameters or {}
    else:
        parameters = fill_default_parameters(tool, explicit_parameters)
    return execute_tool(tool_id, session_id, parameters, search_id, max_response_size)


def walk_dicts(value: Any) -> list[dict[str, Any]]:
    dicts: list[dict[str, Any]] = []
    if isinstance(value, dict):
        dicts.append(value)
        for child in value.values():
            dicts.extend(walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            dicts.extend(walk_dicts(child))
    return dicts


def walk_lists(value: Any) -> list[list[Any]]:
    lists: list[list[Any]] = []
    if isinstance(value, list):
        lists.append(value)
        for child in value:
            lists.extend(walk_lists(child))
    elif isinstance(value, dict):
        for child in value.values():
            lists.extend(walk_lists(child))
    return lists


def key_norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def as_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    multiplier = 1.0
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "").replace(",", "").replace("$", "")
        if cleaned and cleaned[-1].upper() in {"K", "M", "B", "T"}:
            suffix = cleaned[-1].upper()
            cleaned = cleaned[:-1]
            multiplier = {
                "K": 1_000.0,
                "M": 1_000_000.0,
                "B": 1_000_000_000.0,
                "T": 1_000_000_000_000.0,
            }[suffix]
        value = cleaned
    try:
        return float(value) * multiplier
    except (TypeError, ValueError):
        return 0.0


def find_numeric(payload: Any, names: list[str]) -> float:
    targets = [key_norm(name) for name in names]
    for item in walk_dicts(payload):
        normalized = {key_norm(str(key)): val for key, val in item.items()}
        for target in targets:
            if target in normalized:
                number = as_float(normalized[target])
                if number:
                    return number
    return 0.0


def find_text(payload: Any, names: list[str]) -> str:
    targets = [key_norm(name) for name in names]
    for item in walk_dicts(payload):
        normalized = {key_norm(str(key)): val for key, val in item.items()}
        for target in targets:
            if target in normalized and normalized[target] not in (None, ""):
                return str(normalized[target])
    return ""
