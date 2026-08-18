# -*- coding: utf-8 -*-
"""
弥生インポート形式（27列）の仕訳CSVを書き出す。

弥生会計 Next から実際にエクスポートしたCSVの列構成に合わせている。
  文字コード : CP932
  改行       : CRLF
  ヘッダ行   : なし
  列数       : 27（25列版に借方取引先名・貸方取引先名を足したもの）
"""

from dataclasses import dataclass, field
from typing import Optional
import csv
import io

# 識別フラグ。2000 = 仕訳日記帳で入力した形式
SHIKIBETSU_SHIWAKE = "2000"

# 税区分（弥生会計 Next のエクスポート実物から採取）
TAX_OUT = "対象外"
TAX_PURCHASE_10 = "課対仕入込10%適格"
# 弥生会計 Next のエクスポート実物で確認済み
TAX_PURCHASE_8 = "課対仕入込軽減8%適格"


@dataclass
class Entry:
    """1仕訳（単一行の借方・貸方）"""
    date: str                      # YYYY/MM/DD
    debit_account: str             # 借方勘定科目
    debit_amount: int              # 借方金額（税込）
    credit_account: str            # 貸方勘定科目
    credit_amount: int             # 貸方金額（税込）
    summary: str = ""              # 摘要
    debit_tax: str = TAX_OUT       # 借方税区分
    credit_tax: str = TAX_OUT      # 貸方税区分
    slip_no: Optional[int] = None  # 伝票No
    debit_sub: str = ""            # 借方補助科目
    debit_dept: str = ""           # 借方部門
    credit_sub: str = ""
    credit_dept: str = ""
    debit_partner: str = ""        # 借方取引先名
    credit_partner: str = ""

    def to_row(self, slip_no: int) -> list:
        no = self.slip_no if self.slip_no is not None else slip_no
        return [
            SHIKIBETSU_SHIWAKE,      # 1  識別フラグ
            str(no),                 # 2  伝票No
            "",                      # 3  決算
            self.date,               # 4  取引日付
            self.debit_account,      # 5  借方勘定科目
            self.debit_sub,          # 6  借方補助科目
            self.debit_dept,         # 7  借方部門
            self.debit_tax,          # 8  借方税区分
            str(self.debit_amount),  # 9  借方金額
            "0",                     # 10 借方税金額（0=自動計算）
            self.credit_account,     # 11 貸方勘定科目
            self.credit_sub,         # 12 貸方補助科目
            self.credit_dept,        # 13 貸方部門
            self.credit_tax,         # 14 貸方税区分
            str(self.credit_amount), # 15 貸方金額
            "0",                     # 16 貸方税金額
            self.summary,            # 17 摘要
            "",                      # 18 番号
            "",                      # 19 期日
            "0",                     # 20 タイプ
            "",                      # 21 生成元
            "",                      # 22 仕訳メモ
            "",                      # 23 付箋1
            "",                      # 24 付箋2
            "no",                    # 25 調整
            self.debit_partner,      # 26 借方取引先名
            self.credit_partner,     # 27 貸方取引先名
        ]


def write_csv(entries, path: str, start_no: int = 1) -> None:
    """弥生インポート形式で書き出す。CP932・CRLF・ヘッダなし。"""
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    for i, e in enumerate(entries, start=start_no):
        row = e.to_row(i)
        if len(row) != 27:
            raise ValueError(f"列数が27ではありません: {len(row)}")
        w.writerow(row)

    # 弥生が読めない文字が混ざっていれば、ここで落ちる
    data = buf.getvalue().encode("cp932", errors="strict")
    with open(path, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    # 形式確認用のダミー仕訳。実際にインポートできるかを試すためのもの
    entries = [
        Entry(date="2026/08/12",
              debit_account="消耗品費", debit_amount=100716,
              debit_tax=TAX_PURCHASE_10,
              credit_account="買掛金", credit_amount=100716,
              summary="株式会社サンプル電設 SD-2026-0812"),
        Entry(date="2026/08/15",
              debit_account="外注費", debit_amount=1813977,
              debit_tax=TAX_PURCHASE_10,
              credit_account="買掛金", credit_amount=1813977,
              summary="株式会社サンプル電設 SD-2026-0815"),
        Entry(date="2026/08/15",
              debit_account="福利厚生費", debit_amount=54756,
              debit_tax=TAX_PURCHASE_8,
              credit_account="買掛金", credit_amount=54756,
              summary="まるまる商事 MT-260815-03 軽減8%分"),
        Entry(date="2026/08/15",
              debit_account="消耗品費", debit_amount=40238,
              debit_tax=TAX_PURCHASE_10,
              credit_account="買掛金", credit_amount=40238,
              summary="まるまる商事 MT-260815-03 標準10%分"),
        Entry(date="2026/08/13",
              debit_account="消耗品費", debit_amount=38962,
              debit_tax=TAX_PURCHASE_10,
              credit_account="買掛金", credit_amount=38962,
              summary="××資材センター No.4821"),
    ]
    out = "/mnt/user-data/outputs/yayoi_import_test.csv"
    write_csv(entries, out)
    print("wrote", out)
