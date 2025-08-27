# purchase_entry_streamlit.py
import streamlit as st
import pandas as pd
from supabase import create_client
from io import BytesIO

# ========================
# Supabase Config
# ========================
SUPABASE_URL = "https://urgvewvsimsbvzhennkf.supabase.co"
SUPABASE_KEY = "YeyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVyZ3Zld3ZzaW1zYnZ6aGVubmtmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTUwNjI0NjgsImV4cCI6MjA3MDYzODQ2OH0.H_nQhmNVS1S_0C0lFE0yHaiBj0EFTav-LmHtAVnzv-o"  # never use service_role key here
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========================
# Helpers
# ========================
def compute_derived(df):
    df["eq_usd"] = pd.to_numeric(df["amount"], errors="coerce") / pd.to_numeric(df["cross_rate"], errors="coerce")
    df["eq_bdt"] = df["eq_usd"] * pd.to_numeric(df["purchase_rate"], errors="coerce")
    return df

def save_to_supabase(df):
    safe = df.drop(columns=["eq_usd", "eq_bdt"], errors="ignore")
    safe = safe.where(pd.notnull(safe), None)  # NaN → None
    records = safe.to_dict(orient="records")
    supabase.table("purchases").upsert(records).execute()

def download_excel(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Purchases")
    buffer.seek(0)
    return buffer

# ========================
# UI
# ========================
st.title("💰 Purchase Entry App (Streamlit + Supabase)")

# Form to add new entry
with st.form("entry_form"):
    amount = st.number_input("Amount", min_value=0.0, format="%.2f")
    cross_rate = st.number_input("Cross Rate", min_value=0.0, format="%.4f")
    purchase_rate = st.number_input("Purchase Rate", min_value=0.0, format="%.4f")
    exchange_house = st.text_input("Exchange House")
    region = st.text_input("Region")
    country = st.text_input("Country")

    submitted = st.form_submit_button("➕ Add Entry")
    if submitted:
        new_row = pd.DataFrame([{
            "amount": amount,
            "cross_rate": cross_rate,
            "purchase_rate": purchase_rate,
            "exchange_house": exchange_house,
            "region": region,
            "country": country
        }])
        if "df" not in st.session_state:
            st.session_state.df = new_row
        else:
            st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)

# Show table
if "df" in st.session_state and not st.session_state.df.empty:
    st.session_state.df = compute_derived(st.session_state.df)
    st.write("### Current Entries")
    st.dataframe(st.session_state.df)

    # Save to Supabase
    if st.button("💾 Save to Supabase"):
        save_to_supabase(st.session_state.df)
        st.success("Data saved to Supabase!")

    # Export Excel
    excel_data = download_excel(st.session_state.df)
    st.download_button(
        "📥 Download Excel",
        excel_data,
        "purchases.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
