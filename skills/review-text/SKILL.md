---
name: review-text
description: 既存文章のレビュー、推敲、校正、整形、改善。既存メール下書きの推敲も入口はこれだが、文面規範と出力形式は Draft Email / Business Email を優先する。
role: Main
tags: [review, text, japanese, english]
---

# Review Text

指定された文章を、作成者への忖度なくフラットに診断し、必要な工程だけを適用する。修正案を作成する場合は、原意と事実関係を保ちつつ、文章構造を含めて実質的に改善する。

## Procedure

1. 変更範囲と出力モードを特定する。
  - 選択範囲がある場合は、その範囲だけを対象にする。
  - ページや文書全体が指定されている場合は、既存構造に統合して直す。単に末尾へ追記しない。
  - レビューのみ、修正のみ、レビューと修正の両方を区別する。
2. 文種に応じて、目的、読み手、期待する行動を確認する。
  - 原文や依頼から判断できない事項は推測しない。
3. 修正前に問題を診断する。
  - 入力形式の崩れ、意味・論理・情報順序、文章構造、対人表現、表示構造、誤字・表記を分けて確認する。
  - 人に向けた文章では、目的に不要な非難、意図の決めつけ、過剰または不十分な謝罪、根拠に合わない断定、曖昧な依頼を確認する。
4. 問題がある工程だけを適用する。
  - 入力構造が崩れている場合だけ、[書式・表示構造工程](..# local content excludedformatting.md)の「書式正規化（前処理）」を適用する。
  - 文章の意味・論理・読みやすさ・文章構造を改善する必要がある場合だけ、[文章改善工程](..# local content excludedwriting-improvement.md)を適用する。
  - 表示構造だけを整える必要がある場合だけ、[書式・表示構造工程](..# local content excludedformatting.md)の「表示構造整形（最終整形）」を適用する。
  - 完成稿の機械的な誤りを確認する必要がある場合だけ、[最終校正工程](..# local content excludedproofreading.md)を適用する。
  - 誤字、表記揺れ、文法、リンク・メンション破損などは、必要最小限で確認・修正する。
5. 修正後に再評価する。
  - 原意、事実関係、必要な直接性、既存の保護構造を維持しているか確認する。
  - 指摘した問題を解消し、合格していた点を崩していない場合だけ採用する。

## Output

- **レビューコメント**：対象本文には書かず、チャット内に記載する。実質的な問題だけを、問題箇所、理由、修正方針の順で示す。
- **修正案**：指定された文書内の文章を更新する。指定文書がない場合だけ、チャット内に記載する。
- ユーザーが「レビューのみ」「コメントのみ」と指定した場合は、本文を編集しない。

## Hard constraints

- 変更範囲、原意、事実関係、リンク、メンション、表、コード、数式、引用、番号体系を保持する。文章構造の扱いは[編集ガードレール](..# local content excludedediting-guardrails.md)を正とする。
- 原文にない事実、数値、固有名詞、判断、根拠を追加しない。
- 確認できない事項は推測で埋めず、「（要確認）」などで残す。
- メール、議事録、契約、仕様書、手順書、短い業務文書には、ユーザーが明示しない限り[文章リズム規範](..# local content excludedcognitive-rhythm-writing.md)を適用しない。
- 各工程で実質的な改善がない場合は変更しない。

## References

- 変更範囲・原意保持：[編集ガードレール](..# local content excludedediting-guardrails.md)
- 日本語・英語の一般文章規範：[文章基礎規範](..# local content excludedprose-basics.md)
- 技術記事・提案書・調査レポート：[技術文章規範](..# local content excludedtechnical-writing.md)
- Markdown文書：[Markdown表示規範](..# local content excludedmarkdown-formatting.md)
- 人に向けた連絡、説明、依頼、返信、提案：[対人文章規範](..# local content excludedcommunication-writing.md)
- メール文面：[$draft-email](../draft-email/SKILL.md)、[業務メール規範](..# local content excludedbusiness-email.md)
