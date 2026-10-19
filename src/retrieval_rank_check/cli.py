"""Command-line interface for strict retrieval-rank fixture validation."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


HELP = """usage: retrieval-rank-check RUN.jsonl

Validate a UTF-8 JSONL retrieval-rank run without executing retrieval or metrics.
The input rows must contain exactly query, document, and rank fields.
"""
INVALID_OUTPUT = '{"status":"invalid_input"}'


class InvalidInput(Exception):
    """Raised internally for any invalid input; details are never displayed."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidInput
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise InvalidInput


def _unicode_scalar_string(value: str) -> str:
    """Convert valid JSON surrogate pairs and reject unpaired surrogates."""
    result: list[str] = []
    position = 0
    while position < len(value):
        codepoint = ord(value[position])
        if 0xD800 <= codepoint <= 0xDBFF:
            if position + 1 == len(value):
                raise InvalidInput
            low = ord(value[position + 1])
            if not 0xDC00 <= low <= 0xDFFF:
                raise InvalidInput
            result.append(chr(0x10000 + ((codepoint - 0xD800) << 10) + low - 0xDC00))
            position += 2
            continue
        if 0xDC00 <= codepoint <= 0xDFFF:
            raise InvalidInput
        result.append(value[position])
        position += 1
    return "".join(result)


def _parse_line(raw_line: bytes) -> tuple[str, str, int]:
    try:
        text = raw_line.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, InvalidInput, RecursionError, ValueError):
        raise InvalidInput from None
    if not isinstance(value, dict) or set(value) != {"query", "document", "rank"}:
        raise InvalidInput
    query = value["query"]
    document = value["document"]
    rank = value["rank"]
    if not isinstance(query, str) or not query:
        raise InvalidInput
    if not isinstance(document, str) or not document:
        raise InvalidInput
    query = _unicode_scalar_string(query)
    document = _unicode_scalar_string(document)
    if not query or not document:
        raise InvalidInput
    if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 1_000_000:
        raise InvalidInput
    return query, document, rank


def validate_bytes(data: bytes) -> dict[str, object]:
    """Validate complete JSONL bytes and return the contract's deterministic result."""
    if not data:
        return {
            "status": "valid",
            "record_count": 0,
            "query_count": 0,
            "duplicate_rank_lines": [],
            "gap_queries": [],
        }

    # Split only on the three contract delimiters. bytes.splitlines() also
    # treats vertical tab and form feed as boundaries, which JSONL does not.
    lines = re.split(b"\r\n|\r|\n", data)
    if lines[-1] == b"":  # One final record terminator is allowed.
        lines.pop()

    query_indices: dict[str, int] = {}
    seen_pairs: set[tuple[str, str]] = set()
    rank_lines: dict[tuple[str, int], list[int]] = defaultdict(list)
    query_ranks: dict[str, set[int]] = defaultdict(set)
    for line_number, raw_line in enumerate(lines, start=1):
        if not raw_line:
            raise InvalidInput
        query, document, rank = _parse_line(raw_line)
        pair = (query, document)
        if pair in seen_pairs:
            raise InvalidInput
        seen_pairs.add(pair)
        if query not in query_indices:
            query_indices[query] = len(query_indices) + 1
        rank_lines[(query, rank)].append(line_number)
        query_ranks[query].add(rank)

    duplicates = sorted(
        line_number
        for grouped_lines in rank_lines.values()
        if len(grouped_lines) > 1
        for line_number in grouped_lines
    )
    gaps = sorted(
        query_indices[query]
        for query, ranks in query_ranks.items()
        if ranks != set(range(1, len(ranks) + 1))
    )
    has_issues = bool(duplicates or gaps)
    return {
        "status": "rank_issues" if has_issues else "valid",
        "record_count": len(lines),
        "query_count": len(query_indices),
        "duplicate_rank_lines": duplicates,
        "gap_queries": gaps,
    }


def _run(path: str) -> tuple[int, str]:
    try:
        data = Path(path).read_bytes()
        result = validate_bytes(data)
    except (OSError, InvalidInput, ValueError, RecursionError):
        return 2, INVALID_OUTPUT
    return (1 if result["status"] == "rank_issues" else 0), json.dumps(
        result, ensure_ascii=True, separators=(",", ":")
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args in (["-h"], ["--help"]):
        sys.stdout.write(HELP)
        return 0
    if len(args) != 1 or args[0].startswith("-"):
        sys.stdout.write(INVALID_OUTPUT + "\n")
        return 2
    exit_code, output = _run(args[0])
    sys.stdout.write(output + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
