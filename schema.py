# -*- coding: utf-8 -*-
"""
space ocr の POST /ocr/fields に渡す抽出スキーマ。

設計方針
  1. 形式が決まっている項目には pattern / type を宣言する。
     文字照合を待たずに宣言違反として弾けるため。
     （登録番号の O/0 取り違え、日付に混ざった別文字はここで落ちる）
  2. 自由記述の列は review:"off" にする。
     品名の誤字で要確認が埋まると、登録番号や税額に立った印が読めなくなる。
  3. required は「必ず印字される値」だけに付ける。
     無くて当然の項目に付けると missing が量産され、合図が薄まる。
  4. 同じ数字が複数箇所に出る金額には label を添えて座標を安定させる。
"""

# 適格請求書発行事業者の登録番号は T + 数字13桁
REGISTRATION_PATTERN = r"^T\d{13}$"


def invoice_fields():
    return [
        # ── 発行者 ───────────────────────────────
        {
            "name": "issuer",
            "type": "string",
            "required": True,
            "description": "請求書を発行した会社名",
        },
        {
            "name": "registration_no",
            "type": "string",
            "pattern": REGISTRATION_PATTERN,
            "description": "適格請求書発行事業者の登録番号（Tから始まる14桁）",
        },

        # ── 伝票情報 ─────────────────────────────
        {
            "name": "invoice_no",
            "type": "string",
            "description": "請求書番号・伝票番号",
        },
        {
            "name": "issue_date",
            "type": "date",
            "required": True,
            "label": ["発行日", "発行年月日", "日付"],
            "description": "請求書の発行日",
        },
        {
            # 日付型では宣言しない。日本の請求書の支払期限は
            # 「2026年9月末日」「翌月末払い」のように、日付として
            # 解釈できない表記が普通に使われるため。
            # 型を宣言すると正常な請求書が type_mismatch で上がってしまう。
            "name": "due_date",
            "type": "string",
            "label": ["お支払期限", "支払期限", "お支払期日", "支払期日"],
            "description": "支払期限。「月末日」のような表記もそのまま読む",
        },

        # ── 税率ごとの内訳 ───────────────────────
        # 仕訳を切るうえで最も重要な部分。合計だけ合っていても
        # 税率の区分を取り違えると申告額がずれるため、個別に取る。
        {
            "name": "subtotal_10",
            "type": "number",
            "label": ["10%対象 小計", "10%対象", "小計"],
            "description": "標準税率10%の対象金額（税抜または税込の小計）",
        },
        {
            "name": "tax_10",
            "type": "number",
            "label": ["消費税（10%）", "消費税(10%)", "消費税"],
            "description": "標準税率10%分の消費税額",
        },
        {
            "name": "subtotal_8",
            "type": "number",
            "label": ["8%対象 小計", "8%対象"],
            "description": "軽減税率8%の対象金額。軽減税率の記載がなければ空",
        },
        {
            "name": "tax_8",
            "type": "number",
            "label": ["消費税（8%）", "消費税(8%)"],
            "description": "軽減税率8%分の消費税額。記載がなければ空",
        },
        {
            "name": "total",
            "type": "number",
            "required": True,
            "label": ["ご請求金額", "合計", "合　計"],
            "description": "税込の請求合計額",
        },

        # ── 明細 ─────────────────────────────────
        {
            "name": "items",
            "type": "array",
            "description": "明細行",
            "children": [
                # 品名は表記ゆれが大きく、誤字があっても仕訳は成立する。
                # ここで要確認を出すと重要項目の印が埋もれるため off。
                {"name": "name", "type": "string", "review": "off"},
                {"name": "qty", "type": "string"},
                {"name": "unit", "type": "string", "review": "off"},
                {"name": "unit_price", "type": "string"},
                {"name": "amount", "type": "string"},
            ],
        },

        # ── 備考 ─────────────────────────────────
        # 納品と請求のずれを説明する情報が入る。値としては欲しいが
        # 書式が定まらないため要確認は出さない。
        {"name": "note", "type": "string", "review": "off"},
    ]


PROMPT = (
    "日本の請求書です。税率ごとの対象額と消費税額は、明細表の中でも"
    "表の外の注記でも、記載されている場所から読み取ってください。"
    "軽減税率の記載がない請求書では 8% の項目は空で構いません。"
    "印字されていない値は推測せず空にしてください。"
)
