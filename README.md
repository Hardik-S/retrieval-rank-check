# retrieval-rank-check

An offline Python 3.10+ standard-library CLI that validates the structure and rank consistency of normalized retrieval-run JSONL fixtures. It does not run retrieval, metrics, relevance judgments, or scoring. Examples contain synthetic data only.

Install from a checkout with `python -m pip install .`, then run `retrieval-rank-check RUN.jsonl`. Exit codes are 0 for valid data, 1 for rank issues, and 2 for invalid input. The result is one deterministic JSON object on stdout. Invalid input always produces `{"status":"invalid_input"}` without disclosing the path or source content.

Each non-empty physical line must be a UTF-8 JSON object with exactly `query` and `document` non-empty strings and `rank` an integer from 1 through 1,000,000 (booleans are not integers for this schema). Duplicate JSON keys, duplicate exact query/document pairs, malformed JSON, invalid UTF-8, blank records, and invalid schema reject the entire input. CR, LF, and CRLF delimit records. Exact Unicode strings are compared without normalization or case folding.

Duplicate ranks are reported as all physical line numbers sharing a query and rank. Rank gaps are evaluated against the number of distinct ranks for each query; duplicate and gap findings are independent. Query indices follow first appearance. The validator reads the complete input before emitting a result, and memory use grows with input size.

## Examples

```text
retrieval-rank-check examples/valid.jsonl
retrieval-rank-check examples/rank-issues.jsonl
```

Run tests with `python -m pytest` after installing `pytest` in a development environment.
