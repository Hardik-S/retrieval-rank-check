"""Contract tests using synthetic fixture content only."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from retrieval_rank_check.cli import InvalidInput, validate_bytes


def row(query, document, rank):
    return json.dumps({"query": query, "document": document, "rank": rank}, ensure_ascii=False)


def test_empty_and_basic_valid_data():
    assert validate_bytes(b"")["status"] == "valid"
    result = validate_bytes((row("q", "d1", 1) + "\n" + row("q", "d2", 2) + "\n").encode())
    assert result == {
        "status": "valid", "record_count": 2, "query_count": 1,
        "duplicate_rank_lines": [], "gap_queries": [],
    }


@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n"])
@pytest.mark.parametrize("final_terminator", ["", "\n"])
def test_supported_physical_line_endings(newline, final_terminator):
    data = (row("q", "a", 1) + newline + row("q", "b", 2) + final_terminator).encode()
    assert validate_bytes(data)["record_count"] == 2


def test_duplicate_ranks_report_all_lines_and_gap_is_per_query():
    data = "\n".join([row("first", "a", 1), row("first", "b", 1), row("second", "c", 2)])
    assert validate_bytes(data.encode()) == {
        "status": "rank_issues", "record_count": 3, "query_count": 2,
        "duplicate_rank_lines": [1, 2], "gap_queries": [2],
    }


def test_duplicate_rank_and_gap_are_independent():
    assert validate_bytes((row("q", "a", 1) + "\n" + row("q", "b", 1)).encode())["gap_queries"] == []
    assert validate_bytes((row("q", "a", 1) + "\n" + row("q", "b", 3)).encode())["duplicate_rank_lines"] == []
    assert validate_bytes((row("q", "a", 2) + "\n" + row("q", "b", 2)).encode())["gap_queries"] == [1]


def test_query_order_exact_unicode_and_opaque_indices():
    data = "\n".join([row("é", "a", 1), row("e\u0301", "b", 2), row("é", "c", 1)])
    result = validate_bytes(data.encode("utf-8"))
    assert result["query_count"] == 2
    assert result["duplicate_rank_lines"] == [1, 3]
    assert result["gap_queries"] == [2]


def test_json_unicode_surrogate_pair_matches_literal_scalar():
    data = b'{"query":"\\ud83d\\ude00","document":"d","rank":1}\n{"query":"\xf0\x9f\x98\x80","document":"e","rank":1}'
    assert validate_bytes(data)["duplicate_rank_lines"] == [1, 2]


@pytest.mark.parametrize("data", [
    b"\n", b"{}", b'{"query":"q","document":"d","rank":1,"x":0}',
    b'{"query":"q","query":"q","document":"d","rank":1}',
    b'{"query":"q","document":"d","rank":true}',
    b'{"query":"q","document":"d","rank":1.0}',
    b'{"query":"q","document":"d","rank":0}',
    b'{"query":"q","document":"d","rank":1000001}',
    b'{"query":"q","document":"d","rank":NaN}',
    b'{"query":"q","document":"d","rank":Infinity}',
    b'{"query":"q","document":"d","rank":1}\n\n',
    b'{"query":"q","document":"d","rank":1}\v',
    b'{"query":"q","document":"d","rank":1}\xe2\x80\xa8{"query":"r","document":"e","rank":1}',
    b'{"query":"q","document":"d","rank":1}\n{',
    b'{"query":"q","document":"d","rank":1}\n\xff',
    b'{"query":"\\ud800","document":"d","rank":1}',
])
def test_invalid_inputs_raise_without_returning_partial_result(data):
    with pytest.raises(InvalidInput):
        validate_bytes(data)


def test_duplicate_query_document_pair_invalid_even_across_rank():
    data = (row("q", "same", 1) + "\n" + row("q", "same", 2)).encode()
    with pytest.raises(InvalidInput):
        validate_bytes(data)


def test_installed_console_script_contract(tmp_path):
    scripts = Path(sysconfig_scripts())
    executable = scripts / ("retrieval-rank-check.exe" if os.name == "nt" else "retrieval-rank-check")
    valid = tmp_path / "valid.jsonl"
    issue = tmp_path / "issue.jsonl"
    invalid = tmp_path / "secret-private-path.jsonl"
    valid.write_text(row("q", "d", 1) + "\n", encoding="utf-8")
    issue.write_text(row("q", "a", 1) + "\n" + row("q", "b", 3), encoding="utf-8")
    invalid.write_bytes(b"{oops")
    for args, expected_code, expected in [
        ([str(valid)], 0, b'{"status":"valid","record_count":1,"query_count":1,"duplicate_rank_lines":[],"gap_queries":[]}\n'),
        ([str(issue)], 1, b'{"status":"rank_issues","record_count":2,"query_count":1,"duplicate_rank_lines":[],"gap_queries":[1]}\n'),
        ([str(invalid)], 2, b'{"status":"invalid_input"}\n'),
        ([str(invalid), "private-argument"], 2, b'{"status":"invalid_input"}\n'),
        ([], 2, b'{"status":"invalid_input"}\n'),
        (["--private-option"], 2, b'{"status":"invalid_input"}\n'),
        (["--help"], 0, None),
    ]:
        result = subprocess.run([str(executable), *args], capture_output=True, check=False)
        assert result.returncode == expected_code
        assert result.stderr == b""
        if expected is not None:
            assert result.stdout == expected.replace(b"\n", os.linesep.encode())
        else:
            assert b"usage: retrieval-rank-check RUN.jsonl" in result.stdout
    assert str(invalid).encode() not in subprocess.run(
        [str(executable), str(invalid)], capture_output=True
    ).stdout


def sysconfig_scripts():
    import sysconfig
    return sysconfig.get_path("scripts")
