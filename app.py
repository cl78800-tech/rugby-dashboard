import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px

# 1. Page Configuration
st.set_page_config(page_title="Rugby Analytics", layout="wide")
st.title("🏉 Rugby Analytics Engine")

# 2. Secure Supabase Connection
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# 3. Fetch Data
@st.cache_data(ttl=600)
def load_data():
    response = supabase.table('match_events').select("*").execute()
    df = pd.DataFrame(response.data)
    
    if not df.empty:
        df['match_minute'] = pd.to_numeric(df['match_minute'])
        df['impact_points'] = pd.to_numeric(df['impact_points'])
    return df

df = load_data()

# 4. Build the Dashboard
if df.empty:
    st.warning("No data found! Push some XML files through your Colab engine.")
else:
    # --- SIDEBAR FILTERS ---
    st.sidebar.header("Dashboard Filters")
    
    # Competition Dropdown
    comps = ["All"] + sorted(df['competition'].dropna().unique().tolist())
    selected_comp = st.sidebar.selectbox("Competition", comps)
    
    # Filter by Competition first
    comp_df = df if selected_comp == "All" else df[df['competition'] == selected_comp]
    
    # Position Dropdown
    positions = ["All"] + sorted(comp_df['position'].dropna().unique().tolist())
    selected_pos = st.sidebar.selectbox("Position", positions)
    
    # --- DASHBOARD TABS ---
    tab1, tab2 = st.tabs(["⏱️ Match Timeline", "📊 Player Leaderboards"])
    
    # === TAB 1: 80-MINUTE MATCH TIMELINE ===
    with tab1:
        st.subheader("Match Momentum")
        matches = comp_df['match_name'].unique().tolist()
        
        if not matches:
            st.info("No matches found for the selected competition.")
        else:
            selected_match = st.selectbox("Select a Match", matches)
            match_df = comp_df[comp_df['match_name'] == selected_match].copy()
            
            # Sort and calculate running totals
            match_df = match_df.sort_values(by="match_minute")
            match_df['cumulative_impact'] = match_df.groupby('team')['impact_points'].cumsum()
            
            # Build Stepped Line Chart
            fig_timeline = px.line(
                match_df, 
                x="match_minute", 
                y="cumulative_impact", 
                color="team",
                line_shape="hv", 
                hover_data=["player", "action", "impact_points"],
                labels={"match_minute": "Match Minute", "cumulative_impact": "Cumulative Impact"}
            )
            
            # --- THE 80 MINUTE FIX ---
            # This forces the chart to always draw from 0 to 80, placing a tick every 10 mins
            fig_timeline.update_layout(
                xaxis=dict(range=[0, 80], tickmode='linear', dtick=10)
            ) 
            st.plotly_chart(fig_timeline, use_container_width=True)
            
            with st.expander("View Raw Match Data"):
                st.dataframe(match_df)

    # === TAB 2: PLAYER LEADERBOARDS ===
    with tab2:
        st.subheader("Positional Impact Rankings")
        st.write(f"Comparing players across: **{selected_comp}** | Position: **{selected_pos}**")
        
        # Apply the position filter for the leaderboard
        lead_df = comp_df if selected_pos == "All" else comp_df[comp_df['position'] == selected_pos]
        
        if lead_df.empty:
            st.warning("No data found for this specific position in this competition.")
        else:
            # Add up every player's total impact points
            player_totals = lead_df.groupby(['player', 'team', 'position'])['impact_points'].sum().reset_index()
            # Sort them from highest to lowest
            player_totals = player_totals.sort_values(by="impact_points", ascending=False)
            
            # Draw the Bar Chart (Showing the Top 20 players)
            fig_bar = px.bar(
                player_totals.head(20), 
                x="player", 
                y="impact_points", 
                color="team",
                hover_data=["position"],
                title="Top 20 Players by Total Impact",
                labels={"player": "Player", "impact_points": "Total Impact Points"}
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            
            with st.expander("View Full Leaderboard Data"):
                st.dataframe(player_totals)
