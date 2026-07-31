import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. Page Configuration (Must be first)
st.set_page_config(page_title="Rugby League PSV Analytics", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS INJECTION ---
# This forces Streamlit to adopt the styling from your original HTML dashboard
st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background-color: #0B1120;
        color: #E5E7EB;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #374151;
    }
    
    /* Headings */
    h1, h2, h3 {
        color: #F9FAFB !important;
    }
    
    /* Top Banner / Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #1F2937;
        border: 1px solid #374151;
        border-radius: 0.5rem;
        padding: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    /* Dropdown Menus */
    .stSelectbox > div > div {
        background-color: #1F2937;
        color: white;
        border-color: #374151;
    }
    
    /* Dataframes/Tables */
    .stDataFrame {
        background-color: #111827;
        border-radius: 0.5rem;
        border: 1px solid #374151;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
        color: #9CA3AF;
    }
    .stTabs [aria-selected="true"] {
        color: #10B981 !important; /* Your brandAccent color */
        border-bottom: 2px solid #10B981 !important;
    }
    </style>
""", unsafe_allow_html=True)

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

# 3. Fetch Data
@st.cache_data(ttl=600)
def load_data():
    try:
        response = supabase.table('match_events').select("*").execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty:
            df['timestamp_vidref'] = pd.to_numeric(df['timestamp_vidref'])
            df['impact_points'] = pd.to_numeric(df['impact_points'])
            df['match_minute'] = pd.to_numeric(df['match_minute'])
        return df
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return pd.DataFrame()

df = load_data()

# Custom Color Palette (Matching your HTML)
THEME_COLORS = ['#10B981', '#F59E0B', '#3B82F6', '#EC4899', '#8B5CF6', '#EF4444']

# 4. Build the Dashboard
if df.empty:
    st.warning("No data found in the database. Please ensure Colab pushed data successfully.")
else:
    # --- SIDEBAR FILTERS ---
    st.sidebar.markdown("### 📊 Global Filters")
    
    comps = ["All Competitions"] + sorted(df['competition'].dropna().unique().tolist())
    selected_comp = st.sidebar.selectbox("Filter by Competition", comps)
    
    comp_df = df if selected_comp == "All Competitions" else df[df['competition'] == selected_comp]
    
    positions = ["All Positions"] + sorted(comp_df['position'].dropna().unique().tolist())
    selected_pos = st.sidebar.selectbox("Filter by Position", positions)
    
    st.sidebar.markdown("---")
    st.sidebar.info("Data auto-refreshes every 10 minutes.")

    # --- TOP METRICS BANNER ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Total Matches Analyzed", value=comp_df['match_name'].nunique())
    with col2:
        st.metric(label="Total Events Logged", value=f"{len(comp_df):,}")
    with col3:
        st.metric(label="Players Tracked", value=comp_df['player'].nunique())
    with col4:
        avg_impact = comp_df['impact_points'].mean() if not comp_df.empty else 0
        st.metric(label="Avg Impact/Event", value=f"{avg_impact:.2f}")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- DASHBOARD TABS ---
    tab1, tab2, tab3 = st.tabs(["⏱️ Match Timeline (Raw)", "📊 Player Leaderboards", "🔍 Deep Dive Data"])
    
    # === TAB 1: RAW MATCH TIMELINE ===
    with tab1:
        st.markdown("### Match Momentum (Chronological)")
        matches = comp_df['match_name'].unique().tolist()
        
        if not matches:
            st.info("No matches found for the selected filters.")
        else:
            selected_match = st.selectbox("Select a Match to Visualize", matches)
            match_df = comp_df[comp_df['match_name'] == selected_match].copy()
            
            # Use raw video timestamp for perfect ordering
            match_df = match_df.sort_values(by="timestamp_vidref")
            match_df['cumulative_impact'] = match_df.groupby('team')['impact_points'].cumsum()
            
            # Build Stepped Line Chart using dark mode formatting
            fig_timeline = px.line(
                match_df, 
                x="timestamp_vidref", 
                y="cumulative_impact", 
                color="team",
                line_shape="hv", 
                hover_data=["match_minute", "player", "action", "impact_points"],
                color_discrete_sequence=THEME_COLORS
            )
            
            fig_timeline.update_layout(
                plot_bgcolor='rgba(17, 24, 39, 1)', # brandPanel
                paper_bgcolor='rgba(11, 17, 32, 1)', # brandDark
                font_color='#E5E7EB',
                xaxis=dict(showgrid=True, gridcolor='#374151', title="Raw Video Frames (Time)"),
                yaxis=dict(showgrid=True, gridcolor='#374151', title="Cumulative Impact Score"),
                legend_title_text='Team'
            )
            
            st.plotly_chart(fig_timeline, use_container_width=True)

    # === TAB 2: PLAYER LEADERBOARDS ===
    with tab2:
        st.markdown("### Positional Impact Rankings")
        
        lead_df = comp_df if selected_pos == "All Positions" else comp_df[comp_df['position'] == selected_pos]
        
        if lead_df.empty:
            st.warning("No data found for this specific position in this competition.")
        else:
            player_totals = lead_df.groupby(['player', 'team', 'position'])['impact_points'].sum().reset_index()
            player_totals = player_totals.sort_values(by="impact_points", ascending=False)
            
            fig_bar = px.bar(
                player_totals.head(25), 
                x="player", 
                y="impact_points", 
                color="team",
                hover_data=["position"],
                title="Top 25 Players by Total Impact",
                color_discrete_sequence=THEME_COLORS
            )
            
            fig_bar.update_layout(
                plot_bgcolor='rgba(17, 24, 39, 1)',
                paper_bgcolor='rgba(11, 17, 32, 1)',
                font_color='#E5E7EB',
                xaxis=dict(showgrid=False, title="Player Name", tickangle=-45),
                yaxis=dict(showgrid=True, gridcolor='#374151', title="Total Impact Score")
            )
            
            st.plotly_chart(fig_bar, use_container_width=True)

    # === TAB 3: DEEP DIVE DATA ===
    with tab3:
        st.markdown("### Raw Event Log")
        st.markdown("Filter and export raw data for custom analysis.")
        
        # Display the dataframe with Streamlit's built-in filtering and column selection
        st.dataframe(
            comp_df.sort_values(by=['match_name', 'timestamp_vidref'], ascending=[True, True]),
            use_container_width=True,
            hide_index=True
        )
