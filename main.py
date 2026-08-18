# -*- coding: utf-8 -*-
"""
請求書の画像から、弥生会計にそのまま取り込める仕訳CSVを作る。

  python main.py invoices/*.jpg -o out/

  out/
    shiwake.csv        弥生インポート形式（27列・CP932）
    kakunin.csv        人が確認すべき箇所の一覧
    raw/*.json         APIの生レスポンス（再読み取りせず再利用するため）
"""

import argparse
import glob
import json
import os
import sys

import ocr_client
import journal
import schema
from yayoi_csv import write_csv


def process(path, out_raw):
    name = os.path.splitext(os.path.basename(path))[0]
    cache = os.path.join(out_raw, name + ".json")

    # 一度読み取った結果は保存して再利用する。
    # 同じ画像でも読み直すと結果が変わることがあるため、
    # 確定値として扱えるようにしておく。
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        print(f"  {name}: 保存済みの結果を使用")
    else:
        print(f"  {name}: 読み取り中...")
        data = ocr_client.extract_fields(
            path, schema.invoice_fields(), prompt=schema.PROMPT)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return name, journal.build(
        data.get("values", {}),
        data.get("review", {}),
        data.get("normalized", {}),
        source_name=name,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+", help="請求書の画像ファイル")
    ap.add_argument("-o", "--out", default="out", help="出力先ディレクトリ")
    args = ap.parse_args()

    paths = []
    for pat in args.images:
        paths.extend(sorted(glob.glob(pat)) or [pat])

    out_raw = os.path.join(args.out, "raw")
    os.makedirs(out_raw, exist_ok=True)

    all_entries, all_issues = [], []
    print(f"{len(paths)} 件を処理します")

    for p in paths:
        try:
            name, res = process(p, out_raw)
        except Exception as e:
            print(f"  {p}: 失敗 — {e}", file=sys.stderr)
            all_issues.append((os.path.basename(p), "error", "-", str(e)))
            continue

        all_entries.extend(res.entries)
        for i in res.issues:
            all_issues.append((name, i.level, i.where, i.detail))

        mark = "要確認あり" if res.issues else "確認不要"
        print(f"    仕訳 {len(res.entries)} 件 / {mark}")

    csv_path = os.path.join(args.out, "shiwake.csv")
    write_csv(all_entries, csv_path)

    chk_path = os.path.join(args.out, "kakunin.csv")
    import csv as _csv
    with open(chk_path, "w", encoding="utf-8-sig", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["ファイル", "区分", "箇所", "内容"])
        w.writerows(all_issues)

    err = sum(1 for x in all_issues if x[1] == "error")
    warn = sum(1 for x in all_issues if x[1] == "warn")
    print()
    print(f"仕訳       {len(all_entries)} 件  → {csv_path}")
    print(f"要確認     {err + warn} 件（うち要修正 {err} 件） → {chk_path}")
    if err:
        print()
        print("要修正が残っています。取り込む前に kakunin.csv を確認してください。")


if __name__ == "__main__":
    main()
