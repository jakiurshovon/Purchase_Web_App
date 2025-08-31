from io import BytesIO
import pandas as pd
import numpy as np
from typing import List


TEXT_COLS = {"exchange_house", "region", "country", "date", "currency"}
NUMERIC_COLS = {"amount", "cross_rate", "purchase_rate", "eq_usd", "eq_bdt"}




def calc_eq_fields(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Safe numeric
    for c in ["amount", "cross_rate", "purchase_rate"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        else:
            df[c] = 0.0
            df["eq_usd"] = df["amount"] * df["cross_rate"]
            df["eq_bdt"] = df["amount"] * df["purchase_rate"]
    return df




def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        wb = writer.book
        ws = writer.sheets[sheet_name]
        text_fmt = wb.add_format({"align": "left"})
        num_fmt = wb.add_format({"align": "right", "num_format": "#,##0.00"})
        for idx, col in enumerate(df.columns):
            width = max(8, min(40, int(df[col].astype(str).str.len().quantile(0.9)) + 3))
            ws.set_column(idx, idx, width, text_fmt if col.lower() in TEXT_COLS else num_fmt)
        return output.getvalue()




def safe_div(a, b):
    return (a / b) if b not in (0, None, 0.0) else 0.0




def group_summary(df: pd.DataFrame, by: List[str]):
    base = calc_eq_fields(df)
    grp = base.groupby(by, dropna=False, as_index=False).agg(
    amount=("amount", "sum"),
    cross_rate=("cross_rate", "mean"),
    purchase_rate=("purchase_rate", "mean"),
    eq_usd=("eq_usd", "sum"),
    eq_bdt=("eq_bdt", "sum"),
    )
    # Weighted avg purchase rate per USD (EqvBDT/EQUSD)
    grp["weighted_avg"] = grp.apply(lambda r: safe_div(r["eq_bdt"], r["eq_usd"]) if r["eq_usd"] else 0.0, axis=1)
    return grp