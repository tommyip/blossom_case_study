from pathlib import Path

import polars as pl
import streamlit as st

DATA_PATH = Path(__file__).parent.parent / "output" / "companies.parquet"
PODCAST_DIR = Path(__file__).parent.parent / "output" / "podcast"

st.set_page_config(page_title="Blossom Investment Signals", page_icon="🌸", layout="wide")


@st.cache_data
def load_data():
    if not DATA_PATH.exists():
        return None
    return pl.read_parquet(DATA_PATH)


@st.cache_data
def load_podcast_data():
    if not PODCAST_DIR.exists():
        return None, None, None
    analysis = pl.read_parquet(PODCAST_DIR / "guest_analysis.parquet") if (PODCAST_DIR / "guest_analysis.parquet").exists() else None
    episodes = pl.read_parquet(PODCAST_DIR / "all_episodes.parquet") if (PODCAST_DIR / "all_episodes.parquet").exists() else None
    researched = pl.read_parquet(PODCAST_DIR / "researched.parquet") if (PODCAST_DIR / "researched.parquet").exists() else None
    return analysis, episodes, researched


def cro_tab():
    df = load_data()
    if df is None:
        st.error("No data found. Run `uv run python -m src.main` first.")
        return

    # Filters in expander
    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            categories = sorted([c for c in df["nace_category"].unique().to_list() if c])
            selected_cats = st.multiselect("Industry Category", categories, default=[], key="cro_cats")
            tech_only = st.checkbox("Tech companies only", key="cro_tech")
        with col2:
            has_research = st.checkbox("Has research data", value=True, key="cro_research")
            selected_verdicts = []
            if "verdict" in df.columns:
                verdicts = sorted([v for v in df["verdict"].unique().to_list() if v and v != "Unknown"])
                selected_verdicts = st.multiselect("Investment Verdict", verdicts, default=[], key="cro_verdicts")
        with col3:
            selected_stages = []
            if "stage" in df.columns:
                stages = sorted([s for s in df["stage"].unique().to_list() if s and s != "Unknown"])
                selected_stages = st.multiselect("Company Stage", stages, default=[], key="cro_stages")
            search = st.text_input("Search company name", key="cro_search")

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

        display_cols = ["company_name", "verdict", "website", "industry", "stage"]
        display_df = filtered.select([c for c in display_cols if c in filtered.columns])

        if "verdict" in display_df.columns:
            display_df = display_df.sort("verdict", nulls_last=True)

        selection = st.dataframe(
            display_df.to_pandas(),
            use_container_width=True,
            hide_index=True,
            height=600,
            on_select="rerun",
            selection_mode="single-row",
            key="cro_table",
        )

    with right_col:
        st.subheader("Company Detail")

        company_names = display_df["company_name"].to_list()
        if not company_names:
            return

        # Get selected from table click
        selected_idx = 0
        if selection and selection.selection and selection.selection.rows:
            selected_idx = selection.selection.rows[0]

        selected = company_names[selected_idx]
        st.caption(f"Selected: **{selected}**")

        detail = filtered.filter(pl.col("company_name") == selected).to_pandas().iloc[0]

        verdict = detail.get("verdict") or ""
        if "Promising" in verdict:
            st.success(f"**Verdict: Promising** - {detail.get('verdict_reason') or ''}")
        elif "Maybe" in verdict:
            st.warning(f"**Verdict: Maybe** - {detail.get('verdict_reason') or ''}")
        elif "Pass" in verdict:
            st.error(f"**Verdict: Pass** - {detail.get('verdict_reason') or ''}")

        website = detail.get("website")
        if website:
            url = website if website.startswith("http") else f"https://{website}"
            st.markdown(f"🔗 [{website}]({url})")

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

        if detail.get("research_report"):
            st.divider()
            st.markdown(detail.get("research_report"))


def podcast_tab():
    analysis, episodes, researched = load_podcast_data()
    if analysis is None:
        st.error("No podcast data found. Run `uv run python -m src.podcast.scraper` first.")
        return

    # Filters in expander
    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            min_appearances = st.slider("Min appearances", 1, 5, 1, key="pod_appearances")
        with col2:
            min_score = st.slider("Min signal score", 0.0, 20.0, 0.0, key="pod_score")
        with col3:
            high_signal_only = st.checkbox("High-signal only (2+ appearances)", value=False, key="pod_high")

    # Apply filters
    filtered = analysis
    if high_signal_only:
        filtered = filtered.filter(pl.col("high_signal") == True)
    filtered = filtered.filter(pl.col("appearances") >= min_appearances)
    filtered = filtered.filter(pl.col("signal_score") >= min_score)

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_eps = episodes.shape[0] if episodes is not None else 0
        st.metric("Episodes Scanned", f"{total_eps:,}")
    with col2:
        st.metric("Unique Guests", f"{analysis.shape[0]:,}")
    with col3:
        high_count = analysis.filter(pl.col("high_signal") == True).shape[0]
        st.metric("High-Signal Founders", f"{high_count:,}")
    with col4:
        researched_count = researched.shape[0] if researched is not None else 0
        st.metric("Researched", f"{researched_count:,}")

    st.divider()

    # Join research data for table display
    if researched is not None and not researched.is_empty():
        filtered = filtered.join(
            researched.select(["company_name", "funding_total", "latest_round"]),
            on="company_name",
            how="left"
        )

    # Two-column layout
    left_col, right_col = st.columns([2, 3])

    with left_col:
        st.subheader("Founders by Appearances")

        display_cols = ["guest_name", "company_name", "appearances", "unique_podcasts", "signal_score", "funding_total", "latest_round"]
        display_df = filtered.sort("appearances", descending=True).select([c for c in display_cols if c in filtered.columns])

        selection = st.dataframe(
            display_df.to_pandas(),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="podcast_table",
        )

    with right_col:
        st.subheader("Founder Detail")

        guest_names = display_df["guest_name"].to_list()
        if not guest_names:
            return

        # Get selected from table click
        selected_idx = 0
        if selection and selection.selection and selection.selection.rows:
            selected_idx = selection.selection.rows[0]

        selected = guest_names[selected_idx]
        detail = filtered.filter(pl.col("guest_name") == selected).to_pandas().iloc[0]
        company = detail.get("company_name")

        st.markdown(f"### {selected}")
        st.markdown(f"**Company:** {company}")
        st.markdown(f"**Role:** {detail.get('role') or 'N/A'}")

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Appearances", detail.get("appearances"))
        with m2:
            st.metric("Unique Podcasts", detail.get("unique_podcasts"))
        with m3:
            st.metric("Signal Score", f"{detail.get('signal_score'):.1f}")

        if episodes is not None:
            st.divider()
            st.markdown("**Podcast Appearances:**")
            guest_eps = episodes.filter(pl.col("guest_name") == selected).sort("pub_date", descending=True)
            for row in guest_eps.iter_rows(named=True):
                date_str = row["pub_date"][:10] if row["pub_date"] else ""
                link = row.get("link", "")
                title = row.get("episode_title", "")[:60]
                if link:
                    st.markdown(f"- **{row['podcast']}** ({date_str}): [{title}...]({link})")
                else:
                    st.markdown(f"- **{row['podcast']}** ({date_str}): {title}...")

        if researched is not None:
            research_row = researched.filter(pl.col("company_name") == company)
            if research_row.shape[0] > 0:
                r = research_row.to_pandas().iloc[0]
                st.divider()

                likelihood = r.get("fundraise_likelihood") or ""
                if likelihood.lower() == "high":
                    st.success(f"**Fundraise Likelihood: HIGH** | Attractiveness: {r.get('attractiveness_score')}/10")
                elif likelihood.lower() == "medium":
                    st.warning(f"**Fundraise Likelihood: MEDIUM** | Attractiveness: {r.get('attractiveness_score')}/10")
                else:
                    st.info(f"**Fundraise Likelihood: {likelihood}** | Attractiveness: {r.get('attractiveness_score')}/10")

                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Industry:**", r.get("industry") or "N/A")
                    st.write("**Stage:**", r.get("stage") or "N/A")
                    st.write("**Founded:**", r.get("founded_year") or "N/A")
                with c2:
                    st.write("**Funding:**", r.get("funding_total") or "N/A")
                    st.write("**Latest Round:**", r.get("latest_round") or "N/A")
                    st.write("**Employees:**", r.get("employee_count") or "N/A")

                website = r.get("website")
                if website:
                    url = website if website.startswith("http") else f"https://{website}"
                    st.markdown(f"🔗 [{website}]({url})")

                if r.get("research_report"):
                    st.divider()
                    st.markdown("**Research Report:**")
                    st.markdown(r.get("research_report"))


def main():
    st.title("Blossom Investment Signals")

    tab1, tab2 = st.tabs(["🇮🇪 CRO Companies", "🎙️ Podcast Signals"])

    with tab1:
        cro_tab()

    with tab2:
        podcast_tab()


if __name__ == "__main__":
    main()
