import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px

# 1. Page Configuration (Clean Default Theme)
st.set_page_config(page_title="Rugby League PSV Analytics", layout="wide", initial_sidebar_state="expanded")
st.title("🏉 Rugby League PSV Analytics")

# 2. Secure Supabase Connection
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Error connecting to database. Please check Streamlit Secrets.")
        st.stop()

supabase = init_connection()

# 3. Fetch Data (THE FIX: Pagination Loop to bypass the 1,000 row limit)
@st.cache_data(ttl=600)
def load_data():
    all_data = []
    offset = 0
    limit = 1000
    
    with st.spinner("Downloading full database..."):
        while True:
            # Fetch chunks of 1000 rows at a time
            response = supabase.table('match_events').select("*").range(offset, offset + limit - 1).execute()
            data = response.data
            
            if not data:
                break
                
            all_data.extend(data)
            
            # If it returns less than 1000, we've hit the end of the database
            if len(data) < limit:
                break
                
            offset += limit

    df = pd.DataFrame(all_data)
    
    if not df.empty:
        df['timestamp_vidref'] = pd.to_numeric(df['timestamp_vidref'])
        df['impact_points'] = pd.to_numeric(df['impact_points'])
        df['match_minute'] = pd.to_numeric(df['match_minute'])
        
    return df

df = load_data()

# 4. Build the Dashboard
if df.empty:
    st.warning("No data found in the database. Please ensure Colab pushed data successfully.")
else:
    # --- SIDEBAR FILTERS ---
    st.sidebar.markdown("### 📊 Global Filters")
    
    if st.sidebar.button("🔄 Refresh Data Now"):
        st.cache_data.clear()
        st.rerun()
        
    st.sidebar.markdown("---")
    
    comps = ["All Competitions"] + sorted(df['competition'].dropna().unique().tolist())
    selected_comp = st.sidebar.selectbox("Filter by Competition", comps)
    comp_df = df if selected_comp == "All Competitions" else df[df['competition'] == selected_comp]
    
    teams = ["All Teams"] + sorted(comp_df['team'].dropna().unique().tolist())
    selected_team = st.sidebar.selectbox("Filter by Team", teams)
    team_df = comp_df if selected_team == "All Teams" else comp_df[comp_df['team'] == selected_team]
    
    positions = ["All Positions"] + sorted(team_df['position'].dropna().unique().tolist())
    selected_pos = st.sidebar.selectbox("Filter by Position", positions)
    final_df = team_df if selected_pos == "All Positions" else team_df[team_df['position'] == selected_pos]

    # --- TOP METRICS BANNER ---
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric(label="Matches Loaded", value=final_df['match_name'].nunique())
    with col2: st.metric(label="Events Logged", value=f"{len(final_df):,}")
    with col3: st.metric(label="Players Tracked", value=final_df['player'].nunique())
    with col4: st.metric(label="Avg Impact/Event", value=f"{final_df['impact_points'].mean():.2f}" if not final_df.empty else "0")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- DASHBOARD TABS ---
    tab1, tab2, tab3, tab4 = st.tabs(["⏱️ Match Timeline", "📊 Player Leaderboards", "🛡️ Team Overview", "🔍 Raw Data"])
    
    # === TAB 1: RAW MATCH TIMELINE ===
    with tab1:
        st.markdown("### Match Momentum (Chronological)")
        matches = comp_df['match_name'].unique().tolist()
        
        if not matches:
            st.info("No matches found.")
        else:
            selected_match = st.selectbox("Select a Match to Visualize", matches)
            
            # Filter specifically for the selected match
            match_df = comp_df[comp_df['match_name'] == selected_match].copy()
            
            # Sort chronologically to fix the math calculation
            match_df = match_df.sort_values(by="timestamp_vidref")
            
            # Calculate running total per team
            match_df['cumulative_impact'] = match_df.groupby('team')['impact_points'].cumsum()
            
            fig_timeline = px.line(
                match_df, 
                x="timestamp_vidref", 
                y="cumulative_impact", 
                color="team",
                line_shape="hv", 
                hover_data=["player", "action", "impact_points"]
            )
            
            fig_timeline.update_layout(
                xaxis=dict(showgrid=True, title="Raw Video Frames"),
                yaxis=dict(showgrid=True, title="Cumulative Impact Score")
            )
            st.plotly_chart(fig_timeline, use_container_width=True)

    # === TAB 2: PLAYER LEADERBOARDS ===
    with tab2:
        st.markdown("### Positional Impact Rankings")
        if final_df.empty:
            st.warning("No data found for this specific filter.")
        else:
            # Sum up total impact points per player
            player_totals = final_df.groupby(['player', 'team', 'position'])['impact_points'].sum().reset_index()
            player_totals = player_totals.sort_values(by="impact_points", ascending=False)
            
            fig_bar = px.bar(
                player_totals.head(25), 
                x="player", 
                y="impact_points", 
                color="team",
                hover_data=["position"], 
                title="Top 25 Players by Total Impact"
            )
            
            fig_bar.update_layout(
                xaxis=dict(showgrid=False, title="Player Name", tickangle=-45),
                yaxis=dict(showgrid=True, title="Total Impact Score")
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # === TAB 3: TEAM OVERVIEW MATRIX ===
    with tab3:
        st.markdown("### Roster Match-by-Match Breakdown")
        if selected_team == "All Teams":
            st.info("👈 Please select a specific Team from the sidebar to view their roster breakdown.")
        else:
            team_matrix = final_df.pivot_table(
                index=['player', 'position'], 
                columns='match_name', 
                values='impact_points', 
                aggfunc='sum', 
                fill_value=0
            ).reset_index()
            
            match_cols = [col for col in team_matrix.columns if col not in ['player', 'position']]
            team_matrix['Season Total'] = team_matrix[match_cols].sum(axis=1)
            team_matrix = team_matrix.sort_values(by='Season Total', ascending=False)
            
            st.dataframe(team_matrix, use_container_width=True, hide_index=True)

    # === TAB 4: DEEP DIVE DATA ===
    with tab4:
        st.markdown("### Raw Event Log")
        st.dataframe(final_df.sort_values(by=['match_name', 'timestamp_vidref']), use_container_width=True, hide_index=True)
