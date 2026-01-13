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

    # Research filter
    has_research = st.sidebar.checkbox("Has research data", value=True)

    # Verdict filter
    selected_verdicts = []
    if "verdict" in df.columns:
        verdicts = sorted([v for v in df["verdict"].unique().to_list() if v and v != "Unknown"])
        selected_verdicts = st.sidebar.multiselect("Investment Verdict", verdicts, default=[])

    # Stage filter
    selected_stages = []
    if "stage" in df.columns:
        stages = sorted([s for s in df["stage"].unique().to_list() if s and s != "Unknown"])
        selected_stages = st.sidebar.multiselect("Company Stage", stages, default=[])

    # Search
    search = st.sidebar.text_input("Search company name")

    # Apply filters
    filtered = df
    if selected_cats:
        filtered = filtered.filter(pl.col("nace_category").is_in(selected_cats))
    if tech_only:
        filtered = filtered.filter(pl.col("is_tech") == True)
    if has_research and "research_report" in df.columns:
        filtered = filtered.filter(pl.col("research_report").is_not_null())
    if "verdict" in df.columns and selected_verdicts:
        filtered = filtered.filter(pl.col("verdict").is_in(selected_verdicts))
    if "stage" in df.columns and selected_stages:
        filtered = filtered.filter(pl.col("stage").is_in(selected_stages))
    if search:
        filtered = filtered.filter(pl.col("company_name").str.to_lowercase().str.contains(search.lower()))

    # KPI cards
    col1, col2, col3, col4, col5 = st.columns(5)
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
    with col5:
        if "research_report" in filtered.columns:
            research_count = filtered.filter(pl.col("research_report").is_not_null()).shape[0]
            st.metric("With Research", f"{research_count:,}")
        else:
            st.metric("With Research", "N/A")

    st.divider()

    # Charts
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

    st.divider()

    # Two-column layout: table on left, detail on right
    left_col, right_col = st.columns([2, 3])

    with left_col:
        st.subheader("Companies")

        display_cols = [
            "company_name",
            "verdict",
            "website",
            "industry",
            "stage",
        ]
        display_df = filtered.select([c for c in display_cols if c in filtered.columns])

        # Sort by verdict ascending (1-Promising first)
        if "verdict" in display_df.columns:
            display_df = display_df.sort("verdict", nulls_last=True)

        selection = st.dataframe(
            display_df.to_pandas(),
            use_container_width=True,
            hide_index=True,
            height=600,
            on_select="rerun",
            selection_mode="single-row",
        )

    with right_col:
        st.subheader("Company Detail")

        # Use sorted display_df for company names (matches table order)
        company_names = display_df["company_name"].to_list()

        # Get selected company from table click or selectbox
        selected_idx = None
        if selection and selection.selection and selection.selection.rows:
            selected_idx = selection.selection.rows[0]

        if company_names:
            # If a row was clicked, use that; otherwise use selectbox
            default_idx = selected_idx if selected_idx is not None and selected_idx < len(company_names) else 0
            selected = st.selectbox("Select company", company_names, index=default_idx)
            if selected:
                detail = filtered.filter(pl.col("company_name") == selected).to_pandas().iloc[0]

                with st.container(height=600):
                    # Verdict badge
                    verdict = detail.get("verdict") or ""
                    if "Promising" in verdict:
                        st.success(f"**Verdict: Promising** - {detail.get('verdict_reason') or ''}")
                    elif "Maybe" in verdict:
                        st.warning(f"**Verdict: Maybe** - {detail.get('verdict_reason') or ''}")
                    elif "Pass" in verdict:
                        st.error(f"**Verdict: Pass** - {detail.get('verdict_reason') or ''}")

                    # Website link
                    website = detail.get("website")
                    if website:
                        url = website if website.startswith("http") else f"https://{website}"
                        st.markdown(f"🔗 [{website}]({url})")

                    # Company info in two columns
                    info1, info2 = st.columns(2)
                    with info1:
                        st.write("**Company Number:**", detail.get("company_num"))
                        st.write("**Registered:**", detail.get("company_reg_date"))
                        st.write("**NACE Category:**", detail.get("nace_category"))
                        st.write("**Industry:**", detail.get("industry") or "N/A")
                        st.write("**Business Model:**", detail.get("business_model") or "N/A")
                    with info2:
                        st.write("**Stage:**", detail.get("stage") or "N/A")
                        st.write("**Founded:**", detail.get("founded_year") or "N/A")
                        st.write("**Employees:**", detail.get("employee_count") or "N/A")
                        st.write("**Funding:**", detail.get("funding_total") or "N/A")

                    # Research report
                    if detail.get("research_report"):
                        st.divider()
                        st.markdown(detail.get("research_report"))


if __name__ == "__main__":
    main()
