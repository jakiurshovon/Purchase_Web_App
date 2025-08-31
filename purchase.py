import streamlit as st
import pandas as pd
from typing import List
from db import table
from utils import calc_eq_fields
from ui_components import header

PURCHASE_TABLE = "purchases"

BASE_COLS = [
    "date", "exchange_house", "region", "country", "currency",
    "amount", "cross_rate", "purchase_rate",
]
ALL_COLS = BASE_COLS + ["eq_usd", "eq_bdt"]

def list_purchases(filters: dict) -> pd.DataFrame:
    q = table(PURCHASE_TABLE).select("*")
    if filters.get("date_from"):
        q = q.gte("date", str(filters["date_from"]))
    if filters.get("date_to"):
        q = q.lte("date", str(filters["date_to"]))
    if filters.get("country"):
        q = q.eq("country", filters["country"])
    if filters.get("region"):
        q = q.eq("region", filters["region"])
    if filters.get("exchange_house"):
        q = q.eq("exchange_house", filters["exchange_house"])
    res = q.order("date", desc=False).execute()
    rows = res.data or []
    df = pd.DataFrame(rows)
    if len(df) == 0:
        return pd.DataFrame(columns=ALL_COLS)
    # make sure required cols exist
    for c in ALL_COLS:
        if c not in df.columns:
            df[c] = None
    df = calc_eq_fields(df)
    return df[ALL_COLS + (["id"] if "id" in df.columns else [])]


def create_form():
    header(" Purchase Entry")
    with st.form("purchase_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            date = st.date_input("Date")
        currency = st.text_input("Currency", value="USD")
        with c2:
            exchange_house = st.text_input("Exchange House")
        region = st.text_input("Region")
        with c3:
            country = st.text_input("Country")
        amount = st.number_input("Amount", step=0.01, min_value=0.0)
        with c4:
            cross_rate = st.number_input("Cross Rate", step=0.0001,
        min_value=0.0)
        purchase_rate = st.number_input("Purchase Rate", step=0.0001,
        min_value=0.0)
        submitted = st.form_submit_button("Save", type="primary")
        if submitted:
            payload = {
            "date": str(date),
            "currency": currency.strip(),
            "exchange_house": exchange_house.strip(),
            "region": region.strip(),
            "country": country.strip(),
            "amount": float(amount),
            "cross_rate": float(cross_rate),
            "purchase_rate": float(purchase_rate),
            # derived fields stored too (matches your desktop schema behaviour)
            "eq_usd": float(amount) * float(cross_rate),
            "eq_bdt": float(amount) * float(purchase_rate),
            }
            try:
                table(PURCHASE_TABLE).insert(payload).execute()
                st.success("Saved")
            except Exception as e:
                st.error(f"Save failed: {e}")



def edit_grid(filters: dict):
    df = list_purchases(filters)
    st.subheader("Existing Entries")
    edited = st.data_editor(df, key="purchase_grid", use_container_width=True)
    if st.button(" Update Selected/All Changed Rows", type="primary"):
        try:
        # Recompute derived fields
            edited = edited.copy()
            edited["eq_usd"] = edited["amount"].astype(float) * edited["cross_rate"].astype(float)
            edited["eq_bdt"] = edited["amount"].astype(float) * edited["purchase_rate"].astype(float)
            
            # Update rows with id only
            cnt = 0
            id_col = "id" if "id" in edited.columns else None
            if id_col:
                for _, r in edited.iterrows():
                    rid = r.get(id_col)
                    if rid is None:
                        continue
                    payload = {c: r[c] for c in ALL_COLS if c in r}
                    table(PURCHASE_TABLE).update(payload).eq("id",rid).execute()
                    cnt += 1
                st.success(f"Updated {cnt} row(s)")
            else:
                st.info("No id column found; cannot update.")
        except Exception as e:
            st.error(f"Update failed: {e}")