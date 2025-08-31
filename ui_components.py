import streamlit as st
import pandas as pd
from typing import Optional, List




def header(title: str, subtitle: Optional[str] = None):
    st.markdown(f"# {title}")
    if subtitle:
        st.caption(subtitle)




def filters_section(countries: List[str], regions: List[str], houses: List[str]):
    with st.expander("Filters", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            date_from = st.date_input("From")
        with c2:
            date_to = st.date_input("To")
        with c3:
            country = st.selectbox("Country", ["All"] + countries)
        with c4:
            region = st.selectbox("Region", ["All"] + regions)
        house = st.selectbox("Exchange House", ["All"] + houses)
    return {
        "date_from": date_from,
        "date_to": date_to,
        "country": None if country == "All" else country,
        "region": None if region == "All" else region,
        "exchange_house": None if house == "All" else house,
        }




def data_editor(df: pd.DataFrame, key: str = "editor"):
    return st.data_editor(df, key=key, num_rows="dynamic", use_container_width=True)