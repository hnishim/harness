#!/usr/bin/env python3
"""HIR-52 Spike: deterministic Stop-hook grounding fixture runner."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass

URL_RE = re.compile(r"https?://[^\s<>()\]]+")
MD_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")
WORD_RE = re.compile(r"[A-Za-z0-9_]+|[一-龯ぁ-んァ-ヶー]{2,}")
STOPWORDS = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "are", "be", "this", "that", "with", "all"}


@dataclass(frozen=True)
class Citation:
    url: str
    claim: str


def _url(value: str) -> str:
    return value.rstrip(".,;:!?)]}>'\"")


def extract_citations(message: str) -> list[Citation]:
    out: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for line in message.splitlines():
        urls = [_url(m.group(1)) for m in MD_LINK_RE.finditer(line)]
        urls += [_url(m.group(0)) for m in URL_RE.finditer(line)]
        urls = list(dict.fromkeys(urls))
        if not urls:
            continue
        claim = MD_LINK_RE.sub("", line)
        claim = URL_RE.sub("", claim)
        claim = re.sub(r"\s+", " ", claim).strip(" -–—:：")
        for url in urls:
            item = (url, claim)
            if item not in seen:
                seen.add(item)
                out.append(Citation(url, claim))
    return out


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in WORD_RE.findall(text)
        if len(token) >= 2 and token.lower() not in STOPWORDS
    }


def lexical_score(claim: str, source: str) -> float:
    claim_tokens = _tokens(claim)
    if not claim_tokens:
        return 1.0
    return len(claim_tokens & _tokens(source)) / len(claim_tokens)


def assess(claim: str, source: str | None) -> dict[str, object]:
    if source is None:
        return {"result": "unverifiable", "score": None}
    score = round(lexical_score(claim, source), 3)
    return {
        "result": "supported_lexically" if score >= 0.8 else "needs_semantic_judge",
        "score": score,
    }


def semantic_judge_prompt(claim: str, source: str, url: str) -> str:
    return (
        "Use only SOURCE. Classify CLAIM as supported, unsupported, contradicted, "
        "overgeneralized, or unverifiable. Return JSON with label, reason, and "
        "a short evidence excerpt. Do not use outside knowledge.\n"
        f"URL: {url}\nCLAIM: {claim}\nSOURCE:\n{source}"
    )


def evaluate(message: str, sources: dict[str, str]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for citation in extract_citations(message):
        item = assess(citation.claim, sources.get(citation.url))
        results.append({"url": citation.url, "claim": citation.claim, **item})
    return results


def hook_response(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or payload.get("stop_hook_active") is True:
        return {}
    message = payload.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        return {}
    raw_sources = payload.get("hir52_fixture_sources", {})
    sources = raw_sources if isinstance(raw_sources, dict) else {}
    sources = {str(k): str(v) for k, v in sources.items()}
    results = evaluate(message, sources)
    if not results:
        return {}
    unresolved = [r for r in results if r["result"] != "supported_lexically"]
    if not unresolved:
        return {}
    reason = (
        "HIR-52 Spike: cited claims require correction or semantic verification. "
        "The lexical baseline is not a production grounding verdict.\n"
        + "\n".join(
            f"- {r['result']}: claim={r['claim']!r}; url={r['url']}; score={r['score']}"
            for r in unresolved[:5]
        )
    )
    return {"decision": "block", "reason": reason}


def self_test() -> None:
    url = "https://example.test/source"
    assert extract_citations("No URL") == []
    citations = extract_citations(f"CSV is supported [{url}]({url}).\nCSV is supported {url}.")
    assert [c.url for c in citations] == [url, url]
    assert assess("The feature supports CSV exports.", "The feature supports CSV exports.")["result"] == "supported_lexically"
    assert assess("The feature supports enterprise SSO.", "The feature supports CSV exports.")["result"] == "needs_semantic_judge"
    assert assess("Claim", None)["result"] == "unverifiable"
    contradiction = assess("The feature supports SSO.", "The feature does not support SSO.")
    assert contradiction["result"] in {"supported_lexically", "needs_semantic_judge"}
    prompt = semantic_judge_prompt("The feature supports SSO.", "The feature does not support SSO.", url)
    for label in ("supported", "unsupported", "contradicted", "overgeneralized", "unverifiable"):
        assert label in prompt
    payload = {
        "last_assistant_message": f"The feature supports SSO. {url}",
        "stop_hook_active": False,
        "hir52_fixture_sources": {url: "The feature supports CSV exports."},
    }
    assert hook_response(payload)["decision"] == "block"
    payload["stop_hook_active"] = True
    assert hook_response(payload) == {}
    print("HIR-52 fixtures: PASS")


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        self_test()
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    print(json.dumps(hook_response(payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
