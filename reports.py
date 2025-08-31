from io import BytesIO
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from db import table
from utils import group_summary, to_excel_bytes, TEXT_COLS
from ui_components import header


PURCHASE_TABLE = "purchases"


def fetch_df(filters: dict) -> pd.DataFrame:
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
    return pd.DataFrame(res.data or [])
    
    
def build_pdf(df: pd.DataFrame, title: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    story = []
    styles = getSampleStyleSheet()
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 12))
    
    # Convert df to 2D list (header + rows)
    data = [df.columns.tolist()] + df.astype(str).values.tolist()
    t = Table(data, repeatRows=1)
    
    # Left-align text columns; right-align numeric columns
    # Build alignment commands per column
    n_cols = len(df.columns)
    cmds = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    for col_idx, col_name in enumerate(df.columns):
        if col_name.lower() in TEXT_COLS:
            cmds.append(("ALIGN", (col_idx, 0), (col_idx, -1), "LEFT"))
        else:
            cmds.append(("ALIGN", (col_idx, 0), (col_idx, -1), "RIGHT"))
    t.setStyle(TableStyle(cmds))
    story.append(t)
    doc.build(story)
    return buffer.getvalue()



def summary_page(filters: dict):
    header(" Summary Report")
    df = fetch_df(filters)
    if df.empty:
        st.info("No data for selected filters.")
    return
    
    # Modes similar to your desktop app: by House / Region / Country / Currency
    mode = st.radio("Group by", ["Exchange House", "Region", "Country", "Currency"], horizontal=True)
    
    if mode == "Exchange House":
        by = ["exchange_house"]
    elif mode == "Region":
        by = ["region"]
    elif mode == "Country":
        by = ["country"]
    else:
        by = ["currency"]
    
    grp = group_summary(df, by)
    st.dataframe(grp, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        xls = to_excel_bytes(grp, sheet_name=f"Summary_{mode}")
        st.download_button(" Export Excel", data=xls,
        file_name=f"summary_{mode.lower()}.xlsx", mime="application/vnd.openxmlformatsofficedocument.spreadsheetml.sheet")
    with c2:
        pdf = build_pdf(grp, f"Summary Report – {mode}")
        st.download_button(" Export PDF", data=pdf,
        file_name=f"summary_{mode.lower()}.pdf", mime="application/pdf")



def detail_page(filters: dict):
    header(" Detail Report")
    df = fetch_df(filters)
    if df.empty:
        st.info("No data for selected filters.")
    return
    # Column ordering like your desktop app
    cols = [
        "date", "exchange_house", "region", "country", "currency",
        "amount", "cross_rate", "purchase_rate", "eq_usd", "eq_bdt",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]
    st.dataframe(df, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        xls = to_excel_bytes(df, sheet_name="Detail")
        st.download_button(" Export Excel", data=xls, file_name="detail.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") 
    with c2:
        pdf = build_pdf(df, "Detail Report")
        st.download_button(" Export PDF", data=pdf, file_name="detail.pdf", mime="application/pdf")
    
