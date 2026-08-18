# -*- coding: utf-8 -*-
"""
抽出結果から仕訳を組み立てる。

方針は「間違えない」ではなく「間違いを見つけて出す」。
判定に確信が持てない箇所は、黙って埋めずに要確認として残す。
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from yayoi_csv import Entry, TAX_OUT, TAX_PURCHASE_10, TAX_PURCHASE_8

# 相手勘定。買掛金で受けて、支払時に消し込む前提
CREDIT_ACCOUNT = "買掛金"

# 勘定科目の判定ルール。上から順に見て最初に当たったものを採る。
# 電気工事業で実際に出てくる品目を想定している。
ACCOUNT_RULES = [
    ("荷造運賃", ["運搬費", "配送費", "送料", "運賃"]),
    ("雑費", ["諸経費", "雑費", "手数料"]),
    # 「清掃」単体は入れない。「清掃用ゴミ袋」のような消耗品に誤ってあたるため
    ("外注費", ["工事費", "施工", "作業費", "補助作業", "立会",
               "改造費", "設定変更", "片付け", "応援", "常用"]),
    ("福利厚生費", ["弁当", "飲料", "お茶", "飲料水", "食事", "昼食"]),
    ("水道光熱費", ["電気代", "水道", "ガス代", "光熱"]),
    # 弥生の標準勘定科目に合わせて「仕入高」で出す。
    # 「材料費」は標準に無く、取り込みのたびにマッチング画面が出るため。
    ("仕入高", [
        "ケーブル", "電線", "遮断器", "スイッチ", "分電盤", "制御盤",
        "照明", "ライト", "誘導灯", "コンセント", "端子", "金属管",
        "ボックス", "ラック", "支持金具", "配線材",
    ]),
    ("消耗品費", [
        "テープ", "軍手", "手袋", "ビス", "結束バンド", "ドラム",
        "シート", "ゴミ袋", "ペーパー", "工具", "コード",
    ]),
]

# 軽減税率（飲食料品）の判定に使う語。
# ※印がある書類では※を優先し、無い書類でのみこちらを見る。
REDUCED_KEYWORDS = [
    "弁当", "飲料", "飲料水", "お茶", "食品", "食事", "昼食", "菓子", "水",
]


def _norm(s) -> str:
    """全角を半角に畳み、記号を落として比較しやすくする。"""
    if s is None:
        return ""
    return unicodedata.normalize("NFKC", str(s)).strip()


def to_int(s) -> Optional[int]:
    """印字されたままの金額文字列を整数にする。解釈できなければ None。"""
    if s is None:
        return None
    t = _norm(s)
    t = re.sub(r"[¥￥$円,\s]", "", t)
    # 会計式のマイナス表記
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg, t = True, t[1:-1]
    if t.startswith("△") or t.startswith("▲"):
        neg, t = True, t[1:]
    if t.endswith("-"):
        neg, t = True, t[:-1]
    if not re.fullmatch(r"\d+(\.\d+)?", t):
        return None
    v = int(float(t))
    return -v if neg else v


@dataclass
class Issue:
    """人が確認すべき箇所。1件が1行として一覧に出る。"""
    level: str        # "error"（値が誤っている） / "warn"（判定できない）
    where: str        # どのフィールドか
    detail: str

    def __str__(self):
        return f"[{self.level}] {self.where}: {self.detail}"


@dataclass
class Result:
    entries: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    def add(self, level, where, detail):
        self.issues.append(Issue(level, where, detail))

    @property
    def has_error(self):
        return any(i.level == "error" for i in self.issues)


def classify_account(name: str) -> Optional[str]:
    """品名から勘定科目を判定する。当たらなければ None を返す。

    None を返すのは失敗ではなく、人に判断を渡すという意味。
    それらしい科目を当てずっぽうで入れる方が、後から見つけにくい。
    """
    n = _norm(name)
    for account, keywords in ACCOUNT_RULES:
        for kw in keywords:
            if kw in n:
                return account
    return None


def is_reduced(name: str, doc_has_reduced: bool) -> bool:
    """その明細行が軽減税率8%の対象かを判定する。"""
    n = _norm(name)
    # ※印での区分がある書類では、それが最も確かな根拠になる
    if n.startswith("*") or n.startswith("※"):
        return True
    if not doc_has_reduced:
        return False
    return any(kw in n for kw in REDUCED_KEYWORDS)


def _strip_mark(name: str) -> str:
    return re.sub(r"^[※*\s]+", "", _norm(name))


def build(values: dict, review: dict, normalized: dict,
          source_name: str = "") -> Result:
    """抽出結果を仕訳に変換する。

    values     : data.values（印字されたままの値）
    review     : data.review（要確認サマリー）
    normalized : data.normalized（型を宣言した項目の解釈済み値）
    """
    r = Result()
    normalized = normalized or {}

    # ── 1. APIが立てた印をそのまま引き継ぐ ──────────────
    # 宣言違反（pattern / type / missing）は自分で書いた規則なので重い。
    HEAVY = {"pattern_mismatch", "type_mismatch", "out_of_range", "missing"}
    for f in review.get("flagged", []):
        path = f.get("path", "")
        # v2応答は reasons 配列（先頭が代表）。旧形式の単数 reason にも備える。
        reasons = f.get("reasons") or []
        if not reasons and f.get("reason"):
            reasons = [f["reason"]]
        level = "error" if any(x in HEAVY for x in reasons) else "warn"
        r.add(level, path, "OCR側の判定: " + (", ".join(reasons) or "理由なし"))

    issuer = _norm(values.get("issuer"))
    invoice_no = _norm(values.get("invoice_no"))
    reg_no = _norm(values.get("registration_no"))

    # ── 2. 登録番号の妥当性 ─────────────────────────
    # 仕入税額控除の可否に直結するため、最も強く出す。
    if not reg_no:
        r.add("error", "registration_no",
              "登録番号がありません。適格請求書でない可能性があります")
    elif not re.fullmatch(r"T\d{13}", reg_no):
        r.add("error", "registration_no",
              f"登録番号の形式が不正です（{reg_no}）。T＋数字13桁である必要があります")

    # ── 3. 日付 ────────────────────────────────
    issue_date = normalized.get("issue_date") or None
    if not issue_date:
        r.add("error", "issue_date",
              f"発行日を日付として解釈できません（{values.get('issue_date')}）")
        issue_date = ""
    date_str = str(issue_date).replace("-", "/")

    # ── 4. 税率ごとの金額 ───────────────────────────
    sub10 = to_int(values.get("subtotal_10"))
    tax10 = to_int(values.get("tax_10"))
    sub8 = to_int(values.get("subtotal_8"))
    tax8 = to_int(values.get("tax_8"))
    total = to_int(values.get("total"))
    doc_has_reduced = bool(sub8)

    if total is None:
        r.add("error", "total", "合計金額を数値として読めません")

    # 対象額＋消費税＝合計 の検算
    parts = [v for v in (sub10, tax10, sub8, tax8) if v is not None]
    if total is not None and parts:
        calc = sum(parts)
        if calc != total:
            r.add("error", "total",
                  f"内訳の合計{calc:,}円と請求合計{total:,}円が一致しません")

    # ── 5. 明細行 ─────────────────────────────────
    items = values.get("items") or []
    groups = {}          # (勘定科目, 税率) -> 金額合計
    unclassified = []

    for i, it in enumerate(items):
        name = _norm(it.get("name"))
        if not name:
            continue
        qty = to_int(it.get("qty"))
        price = to_int(it.get("unit_price"))
        amount = to_int(it.get("amount"))

        # 数量 × 単価 = 金額 のクロスチェック。
        # 枠が隣の列にまたがって数量を誤読した場合、ここで落ちる。
        if qty is not None and price is not None and amount is not None:
            if qty * price != amount:
                r.add("error", f"items[{i}]",
                      f"{name}: 数量{qty}×単価{price:,}={qty * price:,} が "
                      f"金額{amount:,} と一致しません")

        if amount is None:
            r.add("warn", f"items[{i}]", f"{name}: 金額を数値として読めません")
            continue

        account = classify_account(_strip_mark(name))
        if account is None:
            unclassified.append((i, name, amount))
            account = "仮払金"
            r.add("warn", f"items[{i}]",
                  f"{name}: 勘定科目を判定できません。仮払金で出力しています")

        rate = 8 if is_reduced(name, doc_has_reduced) else 10
        groups[(account, rate)] = groups.get((account, rate), 0) + amount

    # ── 5-2. 明細が税抜か税込かを判定する ────────────────
    # 日本のBtoB請求書は税抜表示が多いが、税込表示のものもある。
    # 弥生の「課対仕入込」は税込入力なので、税抜なら税込に直す必要がある。
    item_total = sum(groups.values())
    declared_ex = sum(v for v in (sub10, sub8) if v is not None)

    tax_included = False
    if groups:
        if total is not None and item_total == total:
            tax_included = True
        elif declared_ex and item_total == declared_ex:
            tax_included = False
        elif declared_ex:
            r.add("warn", "items",
                  f"明細の合計{item_total:,}円が対象額の合計{declared_ex:,}円とも"
                  f"請求合計とも一致しません")

    if not tax_included:
        # 税率ごとに、宣言された消費税額を金額比で按分して税込にする。
        # 端数は最大のグループに寄せ、合計が請求額と一致するようにする。
        tax_by_rate = {10: tax10, 8: tax8}
        sub_by_rate = {10: sub10, 8: sub8}
        for rate in (10, 8):
            keys = [k for k in groups if k[1] == rate]
            if not keys:
                continue
            base = sum(groups[k] for k in keys)
            if base == 0:
                continue
            tax_total = tax_by_rate[rate]
            if tax_total is None:
                # 消費税額の記載がなければ税率から求める
                tax_total = int(base * rate / 100)
            elif sub_by_rate[rate] and sub_by_rate[rate] != base:
                r.add("warn", "items",
                      f"{rate}%分の明細合計{base:,}円が対象額{sub_by_rate[rate]:,}円と"
                      f"一致しません")

            allocated, largest = 0, max(keys, key=lambda k: groups[k])
            for k in keys:
                t = round(tax_total * groups[k] / base)
                allocated += t
                groups[k] += t
            groups[largest] += tax_total - allocated

    # ── 6. 仕訳を組み立てる ─────────────────────────
    # 税率ごとに分けて切る。合計が合っていても区分を混ぜると申告額がずれる。
    # error があるときだけ印を付ける。
    # warn まで含めると全件に印が付き、印そのものが意味を失う。
    flag = "【要確認】" if r.has_error else ""
    base_note = " ".join(x for x in (issuer, invoice_no) if x)

    if not groups and total is not None:
        # 明細が取れなかった場合は、合計だけで1本立てる
        r.add("warn", "items", "明細を取得できませんでした。合計のみで仕訳を作成します")
        r.entries.append(Entry(
            date=date_str, debit_account="仮払金", debit_amount=total,
            debit_tax=TAX_PURCHASE_10,
            credit_account=CREDIT_ACCOUNT, credit_amount=total,
            credit_tax=TAX_OUT,
            summary=f"{flag}{base_note}".strip(),
            credit_partner=issuer,
        ))
        return r

    for (account, rate), amount in sorted(groups.items()):
        tax_code = TAX_PURCHASE_8 if rate == 8 else TAX_PURCHASE_10
        suffix = f" 軽減{rate}%分" if rate == 8 else ""
        r.entries.append(Entry(
            date=date_str,
            debit_account=account, debit_amount=amount, debit_tax=tax_code,
            credit_account=CREDIT_ACCOUNT, credit_amount=amount,
            credit_tax=TAX_OUT,
            summary=f"{flag}{base_note}{suffix}".strip(),
            credit_partner=issuer,
        ))

    # 仕訳の合計と請求額の突合
    if total is not None:
        made = sum(e.debit_amount for e in r.entries)
        if made != total:
            r.add("error", "entries",
                  f"作成した仕訳の合計{made:,}円が請求合計{total:,}円と一致しません")

    return r
