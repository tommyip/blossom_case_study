from pathlib import Path

import polars as pl
import streamlit as st

DATA_PATH = Path(__file__).parent.parent / "output" / "companies.parquet"

st.set_page_config(page_title="Ireland CRO Companies", page_icon="🇮🇪", layout="wide")


@st.cache_data
def load_data():
    if not DATA_PATH.exists():
        return None
    return pl.read_parquet(DATA_PATH)


def main():
    st.title("🇮🇪 Ireland CRO Company Explorer")
    st.caption("Series A Investment Opportunities")

    df = load_data()
    if df is None:
        st.error("No data found. Run `uv run python -m src.main` first.")
        return

    # Sidebar filters
    st.sidebar.header("Filters")

    # Category filter
    categories = sorted([c for c in df["nace_category"].unique().to_list() if c])
    selected_cats = st.sidebar.multiselect("Industry Category", categories, default=[])

    # Tech filter
    tech_only = st.sidebar.checkbox("Tech companies only")

    # Search
    search = st.sidebar.text_input("Search company name")

    # Apply filters
    filtered = df
    if selected_cats:
        filtered = filtered.filter(pl.col("nace_category").is_in(selected_cats))
    if tech_only:
        filtered = filtered.filter(pl.col("is_tech") == True)
    if search:
        filtered = filtered.filter(pl.col("company_name").str.to_lowercase().str.contains(search.lower()))

    # KPI cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Companies", f"{filtered.shape[0]:,}")
    with col2:
        tech_count = filtered.filter(pl.col("is_tech") == True).shape[0]
        st.metric("Tech Companies", f"{tech_count:,}")
    with col3:
        if filtered.shape[0] > 0:
            pct = tech_count / filtered.shape[0] * 100
            st.metric("% Tech", f"{pct:.1f}%")
        else:
            st.metric("% Tech", "0%")
    with col4:
        grant_count = filtered.filter(pl.col("has_eu_grant") == True).shape[0]
        st.metric("With EU Grants", f"{grant_count:,}")

    st.divider()

    # Data table
    st.subheader("Companies")

    display_cols = [
        "company_name",
        "nace_category",
        "is_tech",
        "company_reg_date",
        "company_type",
        "eircode",
    ]
    display_df = filtered.select([c for c in display_cols if c in filtered.columns])

    st.dataframe(
        display_df.to_pandas(),
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    # Charts
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("By Industry Category")
        cat_counts = (
            filtered.group_by("nace_category")
            .len()
            .sort("len", descending=True)
            .head(10)
            .to_pandas()
        )
        st.bar_chart(cat_counts, x="nace_category", y="len")

    with col2:
        st.subheader("Registrations by Year")
        yearly = (
            filtered.with_columns(pl.col("company_reg_date").str.slice(0, 4).alias("year"))
            .group_by("year")
            .len()
            .sort("year")
            .to_pandas()
        )
        st.bar_chart(yearly, x="year", y="len")

    # Detail view
    st.divider()
    st.subheader("Company Detail")
    company_names = filtered["company_name"].to_list()[:100]
    if company_names:
        selected = st.selectbox("Select company", company_names)
        if selected:
            detail = filtered.filter(pl.col("company_name") == selected).to_pandas().iloc[0]
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Company Number:**", detail.get("company_num"))
                st.write("**Type:**", detail.get("company_type"))
                st.write("**Registered:**", detail.get("company_reg_date"))
                st.write("**Category:**", detail.get("nace_category"))
                st.write("**Tech:**", "Yes" if detail.get("is_tech") else "No")
            with col2:
                st.write("**Address:**")
                for i in range(1, 5):
                    addr = detail.get(f"company_address_{i}")
                    if addr:
                        st.write(f"  {addr}")
                st.write("**Eircode:**", detail.get("eircode"))


if __name__ == "__main__":
    main()
