# -*- coding: utf-8 -*-
"""
先方の検証レポートで実際に起きた誤読を再現し、検出できるかを確認する。
APIを呼ばずに journal.build だけを試す。
"""
import journal
from yayoi_csv import write_csv


def show(title, res):
    print("=" * 62)
    print(title)
    print("-" * 62)
    for e in res.entries:
        print(f"  {e.date} {e.debit_account:8s} {e.debit_amount:>10,} "
              f"[{e.debit_tax}] / {e.credit_account}")
        print(f"      摘要: {e.summary}")
    if res.issues:
        print("  要確認:")
        for i in res.issues:
            print("   ", i)
    else:
        print("  要確認: なし")
    print()
    return res


# ── ③ 軽減税率混在。qty「44」の誤読（正しくは4）を再現 ────────
mixed = {
    "issuer": "まるまる商事株式会社",
    "registration_no": "T0000000000001",
    "invoice_no": "MT-260815-03",
    "issue_date": "2026年8月15日",
    "subtotal_10": "36,580", "tax_10": "3,658",
    "subtotal_8": "50,700", "tax_8": "4,056",
    "total": "94,994",
    "items": [
        {"name": "※現場用飲料水 2L×6本", "qty": "8", "unit_price": "1,180", "amount": "9,440"},
        {"name": "※弁当（作業員昼食分）", "qty": "42", "unit_price": "780", "amount": "32,760"},
        {"name": "※お茶パック 100袋入", "qty": "44", "unit_price": "1,450", "amount": "5,800"},
        {"name": "軍手 12双組", "qty": "10", "unit_price": "980", "amount": "9,800"},
        {"name": "養生テープ 50mm", "qty": "24", "unit_price": "320", "amount": "7,680"},
        {"name": "ブルーシート 3.6×5.4", "qty": "6", "unit_price": "1,680", "amount": "10,080"},
        {"name": "※トイレットペーパー 12ロール", "qty": "5", "unit_price": "540", "amount": "2,700"},
        {"name": "清掃用ゴミ袋 45L", "qty": "12", "unit_price": "460", "amount": "5,520"},
        {"name": "配送費", "qty": "1", "unit_price": "3,500", "amount": "3,500"},
    ],
    "note": "※印は軽減税率（8%）対象品目です。",
}
norm_mixed = {"issue_date": "2026-08-15", "total": 94994,
              "subtotal_10": 36580, "tax_10": 3658,
              "subtotal_8": 50700, "tax_8": 4056}
r3 = show("③ 軽減税率混在（数量44の誤読を含む）",
          journal.build(mixed, {"flagged": []}, norm_mixed))

# ── ④ 登録番号の O/0 取り違えを再現 ──────────────────
hand = {
    "issuer": "××資材センター",
    "registration_no": "TO000000000002",
    "invoice_no": "No.4821",
    "issue_date": "2026年8月13日",
    "subtotal_10": "35,420", "tax_10": "3,542",
    "total": "38,962",
    "items": [
        {"name": "プラグ付コード 3m", "qty": "6", "unit_price": "1,240", "amount": "7,440"},
        {"name": "延長ドラム 20m", "qty": "2", "unit_price": "8,600", "amount": "17,200"},
        {"name": "絶縁テープ 黒", "qty": "30", "unit_price": "130", "amount": "3,900"},
        {"name": "圧着端子 R2-4", "qty": "4", "unit_price": "480", "amount": "1,920"},
        {"name": "結束バンド 200mm", "qty": "8", "unit_price": "620", "amount": "4,960"},
    ],
    "note": "※延長ドラム1台は8/14に追加納品",
}
r4 = show("④ 手書き（登録番号 TO... の誤読を含む）",
          journal.build(hand, {"flagged": [
              {"path": "registration_no", "reason": "pattern_mismatch",
               "reasons": ["pattern_mismatch"]}]},
              {"issue_date": "2026-08-13", "total": 38962}))

# ── ① 正常な単票 ────────────────────────────────
ok = {
    "issuer": "株式会社サンプル電設",
    "registration_no": "T0000000000000",
    "invoice_no": "SD-2026-0812",
    "issue_date": "2026年8月12日",
    "subtotal_10": "91,560", "tax_10": "9,156",
    "total": "100,716",
    "items": [
        {"name": "配線用遮断器 30A", "qty": "8", "unit_price": "2,400", "amount": "19,200"},
        {"name": "VVFケーブル 2.0-2C", "qty": "3", "unit_price": "8,600", "amount": "25,800"},
        {"name": "埋込スイッチ", "qty": "12", "unit_price": "380", "amount": "4,560"},
        {"name": "取付工事費", "qty": "1", "unit_price": "42,000", "amount": "42,000"},
    ],
}
r1 = show("① 標準的な単票（誤りなし）",
          journal.build(ok, {"flagged": []},
                        {"issue_date": "2026-08-12", "total": 100716}))

entries = r1.entries + r3.entries + r4.entries
write_csv(entries, "/mnt/user-data/outputs/shiwake_sample.csv")
print(f"CSV書き出し: {len(entries)} 件")
