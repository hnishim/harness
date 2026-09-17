#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(rel: str) -> str:
    path = ROOT / rel
    assert path.is_file(), f"missing required artifact: {rel}"
    return path.read_text(encoding="utf-8")


def require(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle in text, f"missing contract text: {needle!r}"


def forbid(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle not in text, f"obsolete contract text remains: {needle!r}"


def require_regex(text: str, pattern: str, description: str) -> None:
    assert re.search(pattern, text, flags=re.DOTALL), f"missing semantic contract: {description}"


def forbid_regex(text: str, pattern: str, description: str) -> None:
    assert not re.search(pattern, text, flags=re.DOTALL), f"obsolete semantic contract remains: {description}"


def require_state_contract(text: str, state_key: str) -> None:
    needle = f"state_key: {state_key}"
    start = text.find(needle)
    assert start >= 0, f"missing contract text: {needle!r}"
    window = text[max(0, start - 600): start + 2400]
    require_regex(
        window,
        r"(初回|存在しない|ない場合|create|作成)",
        f"{state_key} defines first creation of the state comment",
    )
    require_regex(
        window,
        r"((既存|存在する|ある場合|same|同じ).{0,900}(update|更新))|((update|更新).{0,900}(既存|存在する|ある場合|same|同じ))",
        f"{state_key} updates the existing state comment after creation",
    )
    require_regex(
        window,
        r"(別|separate).{0,250}(Comment|コメント).{0,500}(追加しない|作成しない|保存しない|増やさない|appendしない)",
        f"{state_key} explicitly rejects a second append-only state comment",
    )


def require_anchor_metadata_contract(
    text: str,
    anchor_pattern: str,
    required_patterns: list[tuple[str, str]],
    description: str,
) -> None:
    matches = list(re.finditer(anchor_pattern, text, flags=re.DOTALL))
    assert matches, f"missing metadata contract anchor: {description}"
    for match in matches:
        window = text[max(0, match.start() - 1200): match.end() + 4200]
        if all(re.search(pattern, window, flags=re.DOTALL) for pattern, _ in required_patterns):
            return
    missing = ", ".join(label for _, label in required_patterns)
    raise AssertionError(
        f"missing durable metadata near {description}: expected {missing}"
    )


def require_immutable_event_contract(text: str, event_pattern: str, description: str) -> None:
    matches = list(re.finditer(event_pattern, text, flags=re.DOTALL))
    assert matches, f"missing immutable event class: {description}"
    for match in matches:
        window = text[max(0, match.start() - 600): match.end() + 1000]
        if (
            re.search(r"(immutable event|不変イベント|event Comment)", window, flags=re.DOTALL)
            and re.search(r"(append|新規Comment|新規コメント|新規.{0,120}(Comment|コメント)|追記)", window, flags=re.DOTALL)
        ):
            return
    raise AssertionError(
        f"missing immutable append contract tied to event class: {description}"
    )


canonical = read("skills/implementation-loop/SKILL.md")
planning = read("skills/implementation-loop/references/planning.md")
test_ref = read("skills/implementation-loop/references/test.md")
implementation = read("skills/implementation-loop/references/implementation.md")
spike = read("skills/implementation-loop/references/spike.md")
close_ref = read("skills/implementation-loop/references/close.md")
architecture = read("agent-development-workflow.md")
remote = read("skills/remote-implementation-loop/SKILL.md")
ci = read(".github/workflows/ci.yml")
planning_contract = canonical + "\n" + planning

# HIR-250: current durable workflow state is compacted into one mutable
# comment per logical state while material decisions/findings remain immutable.
require(canonical,
        "可変フェーズ状態",
        "不変イベント",
        "state_key",
        "同じコメントID")
require_regex(
    canonical,
    r"state_key.{0,600}(複数|duplicate|重複).{0,700}BLOCKED",
    "duplicate phase-state keys safe-stop instead of guessing",
)
require_regex(
    canonical,
    r"(承認レビュー|positive Review).{0,900}(更新|update).{0,500}(フェーズ状態|状態コメント|同じコメント)",
    "positive review updates current phase state rather than appending duplicate evidence",
)

require_immutable_event_contract(canonical, r"CHANGES_REQUIRED", "CHANGES_REQUIRED review finding")
require_immutable_event_contract(canonical, r"TESTS_CHANGES_REQUIRED", "TESTS_CHANGES_REQUIRED review finding")
require_immutable_event_contract(canonical, r"PLAN_INCOMPLETE", "PLAN_INCOMPLETE decision")
require_immutable_event_contract(canonical, r"MATERIAL_DEVIATION", "MATERIAL_DEVIATION finding")
require_immutable_event_contract(canonical, r"\bBLOCKED\b", "concrete blocked reason")
require_immutable_event_contract(
    canonical,
    r"ローカル環境.{0,180}受入確認.{0,180}FAIL|Local.{0,120}Acceptance.{0,120}FAIL",
    "Local Acceptance failure",
)
require_immutable_event_contract(
    canonical,
    r"人間.{0,180}受入確認.{0,180}FAIL|Human.{0,120}Acceptance.{0,120}FAIL",
    "Human Acceptance failure",
)
require_immutable_event_contract(
    canonical,
    r"(?:Bug|原因).{0,1200}(?:原因|根拠|証拠)",
    "Bug root-cause evidence",
)
require_immutable_event_contract(
    canonical,
    r"Spike.{0,1400}(?:指摘|主要.{0,120}(?:観測|結果))",
    "Spike material finding",
)
require_immutable_event_contract(
    canonical,
    r"Spike.{0,1400}(?:最終判断|判断)",
    "Spike final decision",
)
require(canonical, "全コメント", "独立", "再取得")

require_anchor_metadata_contract(
    canonical,
    r"可変フェーズ状態",
    [
        (r"state_key", "state key"),
        (r"コメントID", "stable comment id"),
        (
            r"((成果物|候補|候補コミット).{0,220}(SHA|ハッシュ|コミット))|"
            r"((SHA|ハッシュ|コミット).{0,220}(成果物|候補|候補コミット))",
            "current artifact or candidate SHA/hash",
        ),
        (r"レビュー資料", "review packet"),
        (r"レビュー結果", "review result"),
        (r"検証境界", "verification boundary"),
        (r"(unverified|未検証)", "unverified boundary"),
        (r"参照コメントID|コメントID.{0,220}参照", "referenced comment id"),
    ],
    "mutable phase state schema",
)
require_anchor_metadata_contract(
    canonical,
    r"不変イベント",
    [
        (r"(phase|フェーズ)", "phase"),
        (r"state_key", "state key"),
        (
            r"((成果物|候補|候補コミット).{0,220}(SHA|ハッシュ|コミット))|"
            r"((SHA|ハッシュ|コミット).{0,220}(成果物|候補|候補コミット))",
            "artifact or candidate SHA/hash",
        ),
        (r"decision", "decision"),
        (r"(finding|blocker|evidence|証拠|根拠)", "finding/blocker/evidence"),
    ],
    "immutable event schema",
)

require_state_contract(planning, "plan-review")
require_state_contract(test_ref, "test-implementation")
require_state_contract(test_ref, "test-review")
require_state_contract(implementation, "implementation-completion")
require_state_contract(implementation, "implementation-review")
require_state_contract(spike, "spike-result")
require_state_contract(close_ref, "close")
require_regex(
    planning,
    r"レビュー資料.{0,1200}(同じ).{0,500}(コメント|フェーズ状態).{0,1200}レビュー結果",
    "plan-review handoff and result share one mutable state comment",
)
require_regex(
    test_ref,
    r"改訂.{0,1200}(test-implementation|state_key).{0,800}更新",
    "test revisions replace current test implementation state",
)
require_regex(
    close_ref,
    r"(実装完了|結果|受入確認).{0,1200}(コメントID|参照).{0,1500}(クローズ固有|差分)",
    "close state references prior durable state and stores only close-specific delta",
)

require_anchor_metadata_contract(
    planning,
    r"state_key: plan-review",
    [
        (r"レビュー資料", "plan review packet"),
        (r"レビュー結果", "plan review result"),
        (r"(unverified|未検証)", "plan review unverified boundary"),
    ],
    "plan-review state",
)
require_anchor_metadata_contract(
    test_ref,
    r"state_key: test-implementation",
    [
        (r"(成果物|変更ファイル|パス)", "test artifact"),
        (r"(SHA|ハッシュ)", "test artifact hash"),
        (r"(検証境界|未検証|手動確認)", "test verification boundary"),
    ],
    "test-implementation state",
)
require_anchor_metadata_contract(
    implementation,
    r"state_key: implementation-completion",
    [
        (r"(candidate_commit|候補SHA|候補)", "candidate binding"),
        (r"受入確認", "acceptance state"),
        (r"(unverified|未検証)", "acceptance unverified boundary"),
    ],
    "implementation-completion state",
)
require_anchor_metadata_contract(
    spike,
    r"state_key: spike-result",
    [
        (r"(結果|根拠|観測)", "spike result evidence"),
        (r"(判断|Decision)", "spike decision"),
    ],
    "spike-result state",
)
require_anchor_metadata_contract(
    close_ref,
    r"state_key: close",
    [
        (r"(受理済み候補|候補SHA)", "accepted candidate binding"),
        (r"(実装完了|結果|受入確認).{0,1400}(コメントID|参照)", "prior state reference"),
        (r"(公開後CI|最終ステータス)", "close-specific publication metadata"),
    ],
    "close state",
)

forbid_regex(
    planning,
    r"保存後のPlan Review Commentには.{0,1200}Review Context",
    "legacy standalone Plan Review handoff comment contract",
)
forbid_regex(
    planning,
    r"レビュー対象と結果をCommentへ保存",
    "legacy standalone Plan Review result comment contract",
)
forbid_regex(
    test_ref,
    r"変更ファイル.{0,1400}Commentへ保存し\s*`In Test Review`",
    "legacy append-style Test Implementation handoff contract",
)
forbid_regex(
    implementation,
    r"Checkpoint後のCompletion Commentに.{0,2200}保存する",
    "legacy standalone Completion comment contract",
)
forbid_regex(
    implementation,
    r"Implementation ReviewのReview Commentには.{0,1800}保存する",
    "legacy standalone Implementation Review comment contract",
)
forbid_regex(
    spike,
    r"実験結果をCommentへ保存し\s*`In Implementation Review`",
    "legacy append-style Spike result handoff contract",
)
forbid_regex(
    spike,
    r"`DECISION_READY`\s*→.{0,900}Commentへ保存してClose待ち",
    "legacy standalone Spike decision comment contract",
)
forbid_regex(
    close_ref,
    r"Close Commentには最低限.{0,2200}保存します",
    "legacy standalone Close snapshot contract",
)
forbid_regex(
    close_ref,
    r"CI evidenceと再開条件をCommentへ保存してStatusを維持",
    "legacy separate pre-publish CI stop comment contract",
)

for text in (canonical, planning):
    require(text, "HUMAN_AUTHORED_START", "HUMAN_AUTHORED_END")
require_regex(
    canonical,
    r"CODEX_LINEAR_ISSUE_DESCRIPTION_START.{0,1200}(旧形式|互換|正規化|移行)",
    "legacy CODEX marker is compatibility input rather than current ownership source of truth",
)

for text, description in (
    (planning_contract, "canonical planning retains AI-managed CODEX ownership semantics"),
):
    forbid_regex(
        text,
        r"(?:CODEX_LINEAR_ISSUE_DESCRIPTION_(?:START|END)|CODEX.{0,120}マーカー)"
        r".{0,1400}(?:エージェント|AI).{0,240}(?:管理領域|ownership)"
        r".{0,600}(?:として扱う|として管理する|にする|を更新する|を編集する|を変更する|を維持する)",
        description,
    )
    forbid_regex(
        text,
        r"(?:CODEX_LINEAR_ISSUE_DESCRIPTION_(?:START|END)|CODEX.{0,120}マーカー)"
        r".{0,1400}(?:マーカー内|内側|inside).{0,500}"
        r"(?:だけ|のみ)?.{0,100}(?:更新する|編集する|変更する|管理する)",
        description,
    )
    forbid_regex(
        text,
        r"(?:CODEX_LINEAR_ISSUE_DESCRIPTION_(?:START|END)|CODEX.{0,120}マーカー)"
        r".{0,1400}(?:マーカー外|外側|outside).{0,500}"
        r"(?:人間|human).{0,500}(?:領域として扱う|保護対象とみなす|ownership boundary)",
        description,
    )
    forbid_regex(
        text,
        r"(?:CODEX_LINEAR_ISSUE_DESCRIPTION_(?:START|END)|CODEX.{0,120}マーカー)"
        r".{0,1400}(?:新規|current|現行).{0,300}(?:ownership|管理|保護).{0,300}(?:作成する|追加する|維持する)",
        description,
    )

require_regex(
    planning_contract,
    r"HUMAN_AUTHORED.{0,1800}(変更しない|削除しない|保持|保護)|"
    r"(変更しない|削除しない|保持|保護).{0,1800}HUMAN_AUTHORED",
    "canonical planning preserves human-authored protected content",
)
require_regex(
    planning_contract,
    r"CODEX_LINEAR_ISSUE_DESCRIPTION_START.{0,2600}"
    r"((意味内容|内容|既存テキスト).{0,900}(保持|失わ)|"
    r"(保持|失わ).{0,900}(意味内容|内容|既存テキスト))",
    "canonical planning preserves legacy semantic content while normalizing layout",
)
for text, description in (
    (planning_contract, "canonical planning safe-stops on malformed ownership markers"),
):
    require_regex(
        text,
        r"(不正|不整合|壊れ|片側|境界.{0,160}決められない).{0,1800}BLOCKED|"
        r"BLOCKED.{0,1800}(不正|不整合|壊れ|片側|境界.{0,160}決められない)",
        description,
    )
require_regex(
    planning_contract,
    r"(エージェント|AI).{0,900}自動.{0,700}HUMAN_AUTHORED.{0,700}(付けない|付与しない|作成しない)",
    "canonical planning does not automatically add human-authored protection markers",
)
require_regex(
    planning,
    r"基準となる計画.{0,1200}(重複|全文複製).{0,700}(避け|抑制|しない)",
    "canonical plan avoids unnecessary duplication of existing description content",
)
require(planning, "## 承認済みPlan", "## 参考情報")
require_regex(
    planning,
    r"基準となる計画.{0,1600}(一意|1つ|単一).{0,900}(最上位|境界|範囲)",
    "canonical plan has an explicit unique top-level range boundary",
)
forbid(planning, "Markerがなければ既存Descriptionを保持して末尾に1組作成します。")

require_regex(
    close_ref,
    r"(初回クローズ開始|初回開始).{0,2200}(明示的クローズ指示).{0,1800}(state_key: close|クローズ状態).{0,900}(初回作成|作成)",
    "initial Close entry validates the current explicit Close request before creating Close state",
)
require_regex(
    close_ref,
    r"(初回クローズ開始|初回開始).{0,2600}(BLOCKED|未達|不整合|不明).{0,1800}(クローズ状態|state_key: close).{0,700}(作成しない|保存しない|更新しない)",
    "failed initial Close entry does not create or update durable Close permission",
)
require_regex(
    close_ref,
    r"(拒否済み|過去).{0,1200}クローズ指示.{0,1400}(再利用しない|根拠にしない).{0,1600}(新しい|改めて).{0,500}明示的クローズ指示",
    "rejected Close instructions cannot be reused after prerequisites later become true",
)
require_regex(
    close_ref,
    r"(開始条件.{0,240}(通過済み|通過した)|通過済み.{0,240}開始条件).{0,1800}(メタデータ|保存|状態)",
    "started Close state durably identifies that the initial entry gate passed",
)
require_regex(
    close_ref,
    r"開始済みクローズ.{0,2200}(最新状態|再取得).{0,1800}明示的クローズ指示.{0,900}(再要求しない|要求しない)",
    "valid started Close resume does not require a new explicit Close instruction",
)
require_regex(
    close_ref,
    r"開始済みクローズ.{0,2200}entry_gate: passed.{0,700}close_started: true.{0,1400}(受理済み候補|Spike結果).{0,800}参照.{0,800}(整合|一致)",
    "started Close resume is defined by current metadata and accepted-reference consistency",
)
forbid_regex(
    close_ref,
    r"(旧形式|誤作成).{0,1800}(再開|クローズ許可|許可).{0,700}(根拠にしない|扱わない|更新しない|再利用しない|BLOCKED)",
    "Close reference must not special-case legacy or malformed Close states",
)
forbid_regex(
    canonical,
    r"(クローズ状態|state_key: close).{0,2600}(旧形式|誤作成).{0,900}(再開|クローズ許可|許可).{0,700}(根拠にしない|扱わない|更新しない|再利用しない|BLOCKED)",
    "canonical Close state contract must not special-case legacy or malformed states",
)
forbid_regex(
    architecture,
    r"(クローズ|Close).{0,1800}(旧形式|誤作成).{0,900}(再開|クローズ許可|resume|根拠)",
    "architecture Close contract must not retain legacy-state resume rules",
)
require_regex(
    close_ref,
    r"Test required.{0,1000}実装レビュー.{0,600}(クローズ条件にしない|条件にしない|不要)",
    "Test required Close entry does not require Implementation Review",
)
require_regex(
    close_ref,
    r"Test not required.{0,1600}(現在の候補|候補).{0,1200}APPROVE",
    "Test not required Close entry retains current-candidate-bound APPROVE",
)
require_regex(
    canonical,
    r"(クローズ状態|state_key: close).{0,2200}(初回開始|開始条件).{0,2200}(拒否済み|過去).{0,1000}(再利用しない|根拠にしない)",
    "canonical durable-state contract rejects pre-entry Close permission reuse",
)
require_regex(
    architecture,
    r"クローズ.{0,2200}(初回開始|開始境界).{0,2200}(再開|開始済み)",
    "architecture distinguishes initial Close entry from started Close resume",
)

require(architecture, "可変フェーズ状態", "不変")
require(remote, "基準となる", "薄い", "レビューの意味づけ")

require(ci, "python3 skills/implementation-loop/tests/test_linear_persistence_contract.py")

print("[PASS] Linear persistence and Description ownership contract")
