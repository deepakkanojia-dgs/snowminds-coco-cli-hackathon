import os
import streamlit as st
import pandas as pd

st.set_page_config(page_title="PolicySense AI", page_icon="🎯", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))


@st.cache_data(ttl=300)
def load_all_customers():
    return conn.query("SELECT c.customer_id, c.full_name, c.customer_segment, c.churn_risk, c.total_annual_premium, c.overall_sentiment_score, c.city, c.state, c.total_policies, c.active_policies, c.lapsed_policies, c.total_claims, c.rejected_claims, c.pending_claims, c.unresolved_issues, c.tenure_months, c.preferred_channel, c.policy_types, n.recommended_action FROM CUSTOMER_360_DB.ANALYTICS.CUSTOMER_360 c LEFT JOIN CUSTOMER_360_DB.ANALYTICS.NEXT_BEST_ACTION n ON c.customer_id = n.customer_id ORDER BY c.churn_risk DESC, c.overall_sentiment_score ASC")


@st.cache_data(ttl=300)
def load_customer_360(customer_id):
    return conn.query("SELECT * FROM CUSTOMER_360_DB.ANALYTICS.CUSTOMER_360 WHERE customer_id = :1", params=[customer_id])


@st.cache_data(ttl=300)
def load_nba(customer_id):
    return conn.query("SELECT recommended_action FROM CUSTOMER_360_DB.ANALYTICS.NEXT_BEST_ACTION WHERE customer_id = :1", params=[customer_id])


@st.cache_data(ttl=300)
def load_transcripts(customer_id):
    return conn.query("SELECT transcript_id, call_date, call_reason, ROUND(sentiment_score, 3) AS sentiment_score, call_summary, extracted_complaint, churn_indicator FROM CUSTOMER_360_DB.CURATED.CALL_TRANSCRIPTS_ENRICHED WHERE customer_id = :1 ORDER BY call_date DESC", params=[customer_id])


@st.cache_data(ttl=300)
def load_interactions(customer_id):
    return conn.query("SELECT interaction_date, channel, interaction_type, subject, ROUND(sentiment_score, 3) AS sentiment_score, resolved FROM CUSTOMER_360_DB.CURATED.INTERACTIONS_ENRICHED WHERE customer_id = :1 ORDER BY interaction_date DESC", params=[customer_id])


@st.cache_data(ttl=300)
def load_policies(customer_id):
    return conn.query("SELECT policy_id, policy_type, policy_subtype, premium_amount, coverage_amount, status, end_date FROM CUSTOMER_360_DB.RAW.RAW_POLICIES WHERE customer_id = :1 ORDER BY status, policy_type", params=[customer_id])


@st.cache_data(ttl=300)
def load_claims(customer_id):
    return conn.query("SELECT claim_id, claim_date, claim_type, claim_amount, approved_amount, status, satisfaction_score FROM CUSTOMER_360_DB.RAW.RAW_CLAIMS WHERE customer_id = :1 ORDER BY claim_date DESC", params=[customer_id])


def sentiment_color(score):
    if score is None:
        return "gray"
    if score < -0.3:
        return "red"
    if score < 0.2:
        return "orange"
    return "green"


def churn_badge(risk):
    colors = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
    return f"{colors.get(risk, '⚪')} {risk}"


# --- SIDEBAR ---
with st.sidebar:
    st.title("Customer 360")
    st.caption("Insurance | Next Best Action")
    st.divider()
    view_mode = st.radio("View", ["All Customers", "Individual Customer"], index=0)
    if view_mode == "Individual Customer":
        all_df = load_all_customers()
        customer_options = {row["FULL_NAME"]: row["CUSTOMER_ID"] for _, row in all_df.iterrows()}
        selected_name = st.selectbox("Select Customer", options=list(customer_options.keys()), index=0)
        selected_id = customer_options[selected_name]
    st.divider()
    if st.button("Refresh Data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# ===================================================================
# ALL CUSTOMERS VIEW
# ===================================================================
if view_mode == "All Customers":
    st.title("Customer 360 — Portfolio Overview")
    all_df = load_all_customers()

    # --- FILTERS ---
    st.subheader("Filters")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    with filter_col1:
        churn_filter = st.multiselect("Churn Risk", options=["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    with filter_col2:
        segment_filter = st.multiselect("Segment", options=sorted(all_df["CUSTOMER_SEGMENT"].unique().tolist()), default=sorted(all_df["CUSTOMER_SEGMENT"].unique().tolist()))
    with filter_col3:
        city_filter = st.multiselect("City", options=sorted(all_df["CITY"].unique().tolist()), default=[], placeholder="All cities")
    with filter_col4:
        sentiment_range = st.slider("Sentiment Range", min_value=-1.0, max_value=1.0, value=(-1.0, 1.0), step=0.1)

    # Apply filters
    filtered_df = all_df[(all_df["CHURN_RISK"].isin(churn_filter)) & (all_df["CUSTOMER_SEGMENT"].isin(segment_filter)) & (all_df["OVERALL_SENTIMENT_SCORE"] >= sentiment_range[0]) & (all_df["OVERALL_SENTIMENT_SCORE"] <= sentiment_range[1])]
    if city_filter:
        filtered_df = filtered_df[filtered_df["CITY"].isin(city_filter)]

    # --- KPI METRICS ---
    st.divider()
    with st.container(horizontal=True):
        st.metric("Total Customers", len(filtered_df), border=True)
        st.metric("High Risk", len(filtered_df[filtered_df["CHURN_RISK"] == "High"]), border=True)
        st.metric("Total Premium", f"Rs {filtered_df['TOTAL_ANNUAL_PREMIUM'].sum():,.0f}", border=True)
        st.metric("Avg Sentiment", f"{filtered_df['OVERALL_SENTIMENT_SCORE'].mean():.3f}", border=True)
        st.metric("Unresolved Issues", int(filtered_df["UNRESOLVED_ISSUES"].sum()), border=True)

    # --- TABS ---
    tab_ai, tab_dashboard, tab_table, tab_nba = st.tabs(["Ask AI (All Customers)", "Dashboard", "Customer Table", "Next Best Actions"])

    with tab_ai:
        ai_header_col1, ai_header_col2 = st.columns([4, 1])
        with ai_header_col1:
            st.subheader("Ask AI about your entire customer portfolio")
        with ai_header_col2:
            if st.button("New Chat", width="stretch", key="new_chat_portfolio"):
                st.session_state["portfolio_chat"] = []
                st.rerun()

        def build_portfolio_context():
            lines = [f"Portfolio Summary: Total={len(filtered_df)}, High Risk={len(filtered_df[filtered_df['CHURN_RISK'] == 'High'])}, Medium={len(filtered_df[filtered_df['CHURN_RISK'] == 'Medium'])}, Low={len(filtered_df[filtered_df['CHURN_RISK'] == 'Low'])}, Total Premium=Rs {filtered_df['TOTAL_ANNUAL_PREMIUM'].sum():,.0f}, Avg Sentiment={filtered_df['OVERALL_SENTIMENT_SCORE'].mean():.3f}, Unresolved Issues={int(filtered_df['UNRESOLVED_ISSUES'].sum())}"]
            lines.append("\nCustomer Details:")
            for _, row in filtered_df.iterrows():
                lines.append(f"- {row['FULL_NAME']} (ID:{row['CUSTOMER_ID']}) | Segment:{row['CUSTOMER_SEGMENT']} | Churn:{row['CHURN_RISK']} | Premium:Rs {row['TOTAL_ANNUAL_PREMIUM']:,.0f} | Sentiment:{row['OVERALL_SENTIMENT_SCORE']:.3f} | Claims:{row['TOTAL_CLAIMS']} | Unresolved:{row['UNRESOLVED_ISSUES']} | Policies:{row['POLICY_TYPES'] or 'None'} | City:{row['CITY']} | NBA:{str(row['RECOMMENDED_ACTION'])[:150]}")
            return "\n".join(lines)

        PORTFOLIO_SUGGESTIONS = {
            "Who are my top churn risks?": "Which customers are at highest risk of churning and why? List them with their key risk factors.",
            "Revenue at risk": "What is the total premium revenue at risk from high-churn customers? Break it down by customer.",
            "Action priorities": "Prioritize the next best actions across all customers. Which ones should we tackle first and why?",
            "Segment analysis": "Compare customer segments by sentiment, claims, and churn risk. Which segment needs the most attention?",
            "Upsell opportunities": "Which customers have the best upsell or cross-sell potential? What should we offer them?",
        }

        if "portfolio_chat" not in st.session_state:
            st.session_state["portfolio_chat"] = []

        if not st.session_state["portfolio_chat"]:
            selected_suggestion = st.pills("Try asking:", list(PORTFOLIO_SUGGESTIONS.keys()), label_visibility="collapsed")
            if selected_suggestion:
                st.session_state["portfolio_chat"].append({"role": "user", "content": PORTFOLIO_SUGGESTIONS[selected_suggestion]})
                st.rerun()

        with st.form("portfolio_ask_form", clear_on_submit=True):
            prompt_col, btn_col = st.columns([5, 1])
            with prompt_col:
                prompt = st.text_input("Question", placeholder="Ask about all customers...", label_visibility="collapsed")
            with btn_col:
                submitted = st.form_submit_button("Ask", width="stretch")

        if submitted and prompt:
            st.session_state["portfolio_chat"].append({"role": "user", "content": prompt})
            with st.spinner("Analyzing portfolio..."):
                portfolio_context = build_portfolio_context()
                system_prompt = f"You are an insurance customer success AI assistant with access to the full customer portfolio. Answer questions based ONLY on the data provided. Be specific, reference actual customer names, numbers, and data. Provide actionable insights.\n\n{portfolio_context}"
                full_prompt = f"{system_prompt}\n\nUser Question: {prompt}"
                response_df = conn.query("SELECT AI_COMPLETE('mistral-large2', :1) AS response", params=[full_prompt])
                response = response_df.iloc[0]["RESPONSE"]
            st.session_state["portfolio_chat"].append({"role": "assistant", "content": response})
            st.rerun()

        if st.session_state["portfolio_chat"]:
            st.divider()
            show_history = st.toggle("Show chat history", value=True, key="toggle_portfolio_history")
            if show_history:
                for msg in st.session_state["portfolio_chat"]:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])

    with tab_dashboard:
        st.subheader("Portfolio Analytics")

        # Row 1: Churn Risk Distribution + Segment Breakdown
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("**Churn Risk Distribution**")
            churn_counts = filtered_df["CHURN_RISK"].value_counts().reset_index()
            churn_counts.columns = ["Churn Risk", "Count"]
            st.bar_chart(churn_counts, x="Churn Risk", y="Count", color="Churn Risk", horizontal=False)

        with chart_col2:
            st.markdown("**Customers by Segment**")
            segment_counts = filtered_df["CUSTOMER_SEGMENT"].value_counts().reset_index()
            segment_counts.columns = ["Segment", "Count"]
            st.bar_chart(segment_counts, x="Segment", y="Count", color="Segment")

        # Row 2: Premium by Segment + Sentiment Distribution
        chart_col3, chart_col4 = st.columns(2)

        with chart_col3:
            st.markdown("**Total Premium by Segment**")
            premium_by_seg = filtered_df.groupby("CUSTOMER_SEGMENT")["TOTAL_ANNUAL_PREMIUM"].sum().reset_index()
            premium_by_seg.columns = ["Segment", "Total Premium"]
            st.bar_chart(premium_by_seg, x="Segment", y="Total Premium", color="Segment")

        with chart_col4:
            st.markdown("**Sentiment Score Distribution**")
            st.scatter_chart(filtered_df, x="TOTAL_ANNUAL_PREMIUM", y="OVERALL_SENTIMENT_SCORE", color="CHURN_RISK", size="TOTAL_CLAIMS")

        # Row 3: Premium vs Sentiment scatter + City distribution
        chart_col5, chart_col6 = st.columns(2)

        with chart_col5:
            st.markdown("**Claims by Status (All Customers)**")
            claims_data = pd.DataFrame({
                "Status": ["Settled", "Pending", "Rejected"],
                "Count": [int(filtered_df["TOTAL_CLAIMS"].sum() - filtered_df["REJECTED_CLAIMS"].sum() - filtered_df["PENDING_CLAIMS"].sum()), int(filtered_df["PENDING_CLAIMS"].sum()), int(filtered_df["REJECTED_CLAIMS"].sum())]
            })
            st.bar_chart(claims_data, x="Status", y="Count", color="Status")

        with chart_col6:
            st.markdown("**Top Cities by Customer Count**")
            city_counts = filtered_df["CITY"].value_counts().head(10).reset_index()
            city_counts.columns = ["City", "Customers"]
            st.bar_chart(city_counts, x="City", y="Customers")

        # Row 4: Tenure vs Sentiment
        st.markdown("**Customer Tenure vs Sentiment (bubble = premium)**")
        st.scatter_chart(filtered_df, x="TENURE_MONTHS", y="OVERALL_SENTIMENT_SCORE", color="CUSTOMER_SEGMENT", size="TOTAL_ANNUAL_PREMIUM")

    with tab_table:
        st.dataframe(
            filtered_df[["CUSTOMER_ID", "FULL_NAME", "CUSTOMER_SEGMENT", "CHURN_RISK", "TOTAL_ANNUAL_PREMIUM", "OVERALL_SENTIMENT_SCORE", "TOTAL_CLAIMS", "UNRESOLVED_ISSUES", "CITY", "PREFERRED_CHANNEL"]],
            hide_index=True, width="stretch",
            column_config={"TOTAL_ANNUAL_PREMIUM": st.column_config.NumberColumn("Premium", format="Rs %.0f"), "OVERALL_SENTIMENT_SCORE": st.column_config.NumberColumn("Sentiment", format="%.3f")},
        )

    with tab_nba:
        st.subheader("Recommended Actions for All Customers")
        nba_display = filtered_df[["FULL_NAME", "CUSTOMER_SEGMENT", "CHURN_RISK", "TOTAL_ANNUAL_PREMIUM", "RECOMMENDED_ACTION"]].copy()
        nba_display.columns = ["Customer", "Segment", "Churn Risk", "Premium", "Recommended Action"]
        st.dataframe(nba_display, hide_index=True, width="stretch", column_config={"Premium": st.column_config.NumberColumn(format="Rs %.0f")})

# ===================================================================
# INDIVIDUAL CUSTOMER VIEW
# ===================================================================
else:
    cust_df = load_customer_360(selected_id)
    if cust_df.empty:
        st.error("Customer not found.")
        st.stop()

    cust = cust_df.iloc[0]

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.title(f"{cust['FULL_NAME']}")
        st.caption(f"{cust['CUSTOMER_SEGMENT']} | {cust['CITY']}, {cust['STATE']} | Tenure: {cust['TENURE_MONTHS']} months | ID: {selected_id}")
    with col_h2:
        st.markdown(f"### Churn Risk: {churn_badge(cust['CHURN_RISK'])}")

    # NBA
    nba_df = load_nba(selected_id)
    if not nba_df.empty:
        with st.container(border=True):
            st.subheader("Next Best Action")
            st.info(nba_df.iloc[0]["RECOMMENDED_ACTION"])

    # KPIs
    with st.container(horizontal=True):
        st.metric("Annual Premium", f"Rs {cust['TOTAL_ANNUAL_PREMIUM']:,.0f}", border=True)
        st.metric("Active Policies", f"{cust['ACTIVE_POLICIES']}", border=True)
        st.metric("Total Claims", f"{cust['TOTAL_CLAIMS']}", border=True)
        st.metric("Sentiment Score", f"{cust['OVERALL_SENTIMENT_SCORE']:.2f}", border=True)
        st.metric("Unresolved Issues", f"{cust['UNRESOLVED_ISSUES']}", border=True)

    # TABS
    tab_chat, tab_timeline, tab_calls, tab_interactions, tab_policies, tab_claims, tab_profile = st.tabs(["Ask AI", "Sentiment Timeline", "Call Transcripts", "Interactions", "Policies", "Claims", "Profile"])

    with tab_chat:
        chat_header_col1, chat_header_col2 = st.columns([4, 1])
        with chat_header_col1:
            st.subheader("Ask about this customer")
        with chat_header_col2:
            chat_key = f"chat_{selected_id}"
            if st.button("New Chat", width="stretch", key=f"new_chat_{selected_id}"):
                st.session_state[chat_key] = []
                st.rerun()

        def build_customer_context():
            context = f"Customer: {cust['FULL_NAME']} | Segment: {cust['CUSTOMER_SEGMENT']} | Tenure: {cust['TENURE_MONTHS']} months | Premium: Rs {cust['TOTAL_ANNUAL_PREMIUM']:,.0f} | Active Policies: {cust['ACTIVE_POLICIES']} | Lapsed: {cust['LAPSED_POLICIES']} | Policy Types: {cust['POLICY_TYPES'] or 'None'} | Claims: {cust['TOTAL_CLAIMS']} (Settled:{cust['SETTLED_CLAIMS']}, Rejected:{cust['REJECTED_CLAIMS']}, Pending:{cust['PENDING_CLAIMS']}) | Satisfaction: {cust['AVG_CLAIM_SATISFACTION'] or 'N/A'}/5 | Sentiment: {cust['OVERALL_SENTIMENT_SCORE']} | Churn Risk: {cust['CHURN_RISK']} | Unresolved: {cust['UNRESOLVED_ISSUES']} | Channel: {cust['PREFERRED_CHANNEL']} | Credit: {cust['CREDIT_SCORE']} | Income: Rs {cust['ANNUAL_INCOME']:,.0f}"
            transcripts_ctx = load_transcripts(selected_id)
            if not transcripts_ctx.empty:
                context += "\n\nCall Transcripts:"
                for _, t in transcripts_ctx.iterrows():
                    context += f"\n- [{t['CALL_DATE']}] {t['CALL_REASON']} | Sentiment:{t['SENTIMENT_SCORE']} | Summary:{str(t['CALL_SUMMARY'])[:200]}"
            interactions_ctx = load_interactions(selected_id)
            if not interactions_ctx.empty:
                context += "\n\nInteractions:"
                for _, i in interactions_ctx.iterrows():
                    context += f"\n- [{i['INTERACTION_DATE']}] {i['CHANNEL']} - {i['SUBJECT']} | Sentiment:{i['SENTIMENT_SCORE']} | Resolved:{i['RESOLVED']}"
            nba_ctx = load_nba(selected_id)
            if not nba_ctx.empty:
                context += f"\n\nNext Best Action: {nba_ctx.iloc[0]['RECOMMENDED_ACTION']}"
            return context

        SUGGESTIONS = {
            "Why is this customer at risk?": "Why is this customer at risk of churning?",
            "What should we do next?": "What is the recommended next best action and why?",
            "Summarize recent calls": "Summarize the recent call interactions and their sentiment",
            "Upsell opportunities": "What upsell or cross-sell opportunities exist for this customer?",
        }

        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        if not st.session_state[chat_key]:
            selected_suggestion = st.pills("Try asking:", list(SUGGESTIONS.keys()), label_visibility="collapsed")
            if selected_suggestion:
                st.session_state[chat_key].append({"role": "user", "content": SUGGESTIONS[selected_suggestion]})
                st.rerun()

        with st.form(f"ask_form_{selected_id}", clear_on_submit=True):
            prompt_col, btn_col = st.columns([5, 1])
            with prompt_col:
                prompt = st.text_input("Question", placeholder="Ask about this customer...", label_visibility="collapsed")
            with btn_col:
                submitted = st.form_submit_button("Ask", width="stretch")

        if submitted and prompt:
            st.session_state[chat_key].append({"role": "user", "content": prompt})
            with st.spinner("Thinking..."):
                customer_context = build_customer_context()
                system_prompt = f"You are an insurance customer success AI assistant. Answer questions based ONLY on this data. Be specific and actionable.\n\n{customer_context}"
                full_prompt = f"{system_prompt}\n\nUser Question: {prompt}"
                response_df = conn.query("SELECT AI_COMPLETE('mistral-large2', :1) AS response", params=[full_prompt])
                response = response_df.iloc[0]["RESPONSE"]
            st.session_state[chat_key].append({"role": "assistant", "content": response})
            st.rerun()

        if st.session_state[chat_key]:
            st.divider()
            show_history = st.toggle("Show chat history", value=True, key=f"toggle_history_{selected_id}")
            if show_history:
                for msg in st.session_state[chat_key]:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])

    with tab_timeline:
        st.subheader("Sentiment Over Time")
        # Combine calls and interactions into a timeline
        transcripts_tl = load_transcripts(selected_id)
        interactions_tl = load_interactions(selected_id)

        timeline_data = []
        if not transcripts_tl.empty:
            for _, t in transcripts_tl.iterrows():
                timeline_data.append({"Date": pd.to_datetime(t["CALL_DATE"]), "Sentiment": t["SENTIMENT_SCORE"], "Source": "Call", "Detail": t["CALL_REASON"]})
        if not interactions_tl.empty:
            for _, i in interactions_tl.iterrows():
                timeline_data.append({"Date": pd.to_datetime(i["INTERACTION_DATE"]), "Sentiment": i["SENTIMENT_SCORE"], "Source": i["CHANNEL"], "Detail": i["SUBJECT"]})

        if timeline_data:
            tl_df = pd.DataFrame(timeline_data).sort_values("Date")
            st.line_chart(tl_df, x="Date", y="Sentiment", color="Source")

            st.divider()
            st.markdown("**Interaction Timeline**")
            for _, row in tl_df.iterrows():
                color = sentiment_color(row["Sentiment"])
                st.markdown(f":{color}[●] **{row['Date'].strftime('%Y-%m-%d')}** | {row['Source']} | {row['Detail']} | Sentiment: {row['Sentiment']:.3f}")
        else:
            st.info("No interactions recorded to show timeline.")

        # Policy breakdown pie-like chart
        policies_viz = load_policies(selected_id)
        if not policies_viz.empty:
            st.divider()
            st.markdown("**Premium Distribution by Policy Type**")
            premium_dist = policies_viz.groupby("POLICY_TYPE")["PREMIUM_AMOUNT"].sum().reset_index()
            premium_dist.columns = ["Policy Type", "Premium"]
            st.bar_chart(premium_dist, x="Policy Type", y="Premium", color="Policy Type")

    with tab_calls:
        transcripts = load_transcripts(selected_id)
        if transcripts.empty:
            st.info("No call transcripts recorded for this customer.")
        else:
            for _, t in transcripts.iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    with col1:
                        st.markdown(f"**{t['CALL_REASON']}**")
                        st.caption(f"{t['CALL_DATE']}")
                    with col2:
                        st.markdown(f"Sentiment: **{t['SENTIMENT_SCORE']}**")
                    with col3:
                        color = sentiment_color(t["SENTIMENT_SCORE"])
                        st.markdown(f":{color}[{'●' * 3}]")
                    if t["CALL_SUMMARY"]:
                        st.markdown(f"**Summary:** {str(t['CALL_SUMMARY'])[:500]}")
                    if t["EXTRACTED_COMPLAINT"]:
                        st.markdown(f"**Issue:** {t['EXTRACTED_COMPLAINT']}")
                    if t["CHURN_INDICATOR"]:
                        st.markdown(f"**Churn Signal:** {t['CHURN_INDICATOR']}")

    with tab_interactions:
        interactions = load_interactions(selected_id)
        if interactions.empty:
            st.info("No interactions recorded for this customer.")
        else:
            st.dataframe(interactions, hide_index=True, width="stretch", column_config={"SENTIMENT_SCORE": st.column_config.NumberColumn(format="%.3f"), "RESOLVED": st.column_config.CheckboxColumn()})

    with tab_policies:
        policies = load_policies(selected_id)
        if policies.empty:
            st.info("No policies found.")
        else:
            st.dataframe(policies, hide_index=True, width="stretch", column_config={"PREMIUM_AMOUNT": st.column_config.NumberColumn("Premium", format="Rs %.0f"), "COVERAGE_AMOUNT": st.column_config.NumberColumn("Coverage", format="Rs %.0f")})

    with tab_claims:
        claims = load_claims(selected_id)
        if claims.empty:
            st.info("No claims found.")
        else:
            st.dataframe(claims, hide_index=True, width="stretch", column_config={"CLAIM_AMOUNT": st.column_config.NumberColumn("Claimed", format="Rs %.0f"), "APPROVED_AMOUNT": st.column_config.NumberColumn("Approved", format="Rs %.0f"), "SATISFACTION_SCORE": st.column_config.NumberColumn("Satisfaction", format="%d/5")})

    with tab_profile:
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.subheader("Customer Profile")
                st.markdown(f"- **Email:** {cust['EMAIL']}\n- **Phone:** {cust['PHONE']}\n- **Income:** Rs {cust['ANNUAL_INCOME']:,.0f}\n- **Credit Score:** {cust['CREDIT_SCORE']}\n- **Preferred Channel:** {cust['PREFERRED_CHANNEL']}")
        with col2:
            with st.container(border=True):
                st.subheader("Claims Summary")
                st.markdown(f"- **Total Claimed:** Rs {cust['TOTAL_AMOUNT_CLAIMED']:,.0f}\n- **Total Approved:** Rs {cust['TOTAL_AMOUNT_APPROVED']:,.0f}\n- **Avg Resolution:** {cust['AVG_RESOLUTION_DAYS'] or 'N/A'} days\n- **Avg Satisfaction:** {cust['AVG_CLAIM_SATISFACTION'] or 'N/A'}/5\n- **Rejected Claims:** {cust['REJECTED_CLAIMS']}")
