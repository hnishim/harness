---
name: translate
description: 選択範囲またはプロンプト内の文章を翻訳する。ページ全体の対訳版は Add English Version を使う。
role: Main
tags: [translation, japanese, english]
---

# Translate

選択範囲またはプロンプト内の文章を翻訳する。翻訳内容は[翻訳規範](../writing-references/translation-rules.md)、変更範囲と保護構造は[編集ガードレール](../writing-references/editing-guardrails.md)を正とする。

## Procedure

1. 対象範囲と出力先を確認する。
  - 選択範囲がある場合は、その範囲だけを対象にする。
  - プロンプト内の文章を訳す場合は、チャットに出力する。
2. 翻訳の用途を判定する。
  - 用途Aまたは用途Bの判定基準は[翻訳規範](../writing-references/translation-rules.md)に従う。
  - [翻訳規範](../writing-references/translation-rules.md)で用途を一意に判定できない場合は確認する。
3. 翻訳する。
  - 訳出方向の指定があれば指定に従い、指定がなければ[翻訳規範](../writing-references/translation-rules.md)の既定方向に従う。
  - 用途、専門用語、保持要素、混在言語、不明箇所の扱いは[翻訳規範](../writing-references/translation-rules.md)に従う。
4. 出力する。
  - 選択範囲がある場合は、原文を削除・差し替えず、訳文を原文の下部に差し込む。入れ替え・差し替え指示がある場合のみ例外とする。
  - プロンプト内の文章はチャットに出力する。

## Output

- 感想、要約、余分な見出しは追加しない。

## Hard constraints

- 翻訳規範と編集ガードレールに定める不変条件を守り、未確認情報を推測せず、既存のリンク、メンション、コード、数式、表、ファイルを壊さない。
