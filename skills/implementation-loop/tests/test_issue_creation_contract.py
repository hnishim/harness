#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "create-issue" / "SKILL.md"

assert SKILL.is_file(), "skills/create-issue/SKILL.md must exist"
text = SKILL.read_text(encoding="utf-8")

for required in (
    "何を解決",
    "期待",
    "制約",
    "Description",
    "Plan",
):
    assert required in text, f"create-issue skill missing contract concept: {required}"

assert "リポジトリ" in text
assert any(term in text for term in ("推測しない", "推測して", "未確認", "確認前"))
assert any(term in text for term in ("対象ファイル", "ファイルパス", "実装手順"))
assert any(term in text for term in ("テスト方法", "テスト手順", "検証方法"))

assert any(term in text for term in ("同じコメント", "同一コメント", "1件"))
assert any(term in text for term in ("初稿", "未承認"))
assert any(term in text for term in ("詳細", "仕様", "設計"))
assert any(term in text for term in ("Planning", "計画作成"))

assert any(term in text for term in ("単純", "簡単"))
assert any(term in text for term in ("短いDescription", "Descriptionのみ"))
assert any(term in text for term in ("Plan初稿", "Planコメント"))

print("[PASS] create-issue skill keeps Description concise and reuses one mutable Plan draft")
