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
@st.cache_data(ttl=600) # Caches the data for 10 mins so it's lightning fast
def load_data():
    # Grabs all data from your table
    response = supabase.table('match_events').select("*").execute()
    df = pd.DataFrame(response.data)
    
    # Ensure our axes are numeric
    if not df.empty:
        df['match_minute'] = pd.to_numeric(df['match_minute'])
        df['impact_points'] = pd.to_numeric(df['impact_points'])
    return df

df = load_data()

# 4. Build the Dashboard
# Filter the dataframe based on the dropdown
    match_df = df[df['match_name'] == selected_match].copy()
    
    # --- THE UPGRADE: CUMULATIVE MOMENTUM ---
    # 1. Sort chronologically (Crucial for running totals)
    match_df = match_df.sort_values(by="match_minute")
    
    # 2. Calculate the running total of impact points for each team
    match_df['cumulative_impact'] = match_df.groupby('team')['impact_points'].cumsum()
    
    # 3. Build the Stepped Line Chart
    st.subheader(f"Match Momentum: {selected_match}")
    
    fig = px.line(
        match_df, 
        x="match_minute", 
        y="cumulative_impact", 
        color="team",
        line_shape="hv", # Creates the professional "stepped" look
        hover_data=["player", "action", "impact_points"],
        title="Team Momentum (Running Total of Impact Points)",
        labels={"match_minute": "Match Minute", "cumulative_impact": "Cumulative Impact"}
    )
    
    # Make the chart look professional
    fig.update_layout(xaxis=dict(tickmode='linear', dtick=10)) 
    st.plotly_chart(fig, use_container_width=True)
    
    # Show the raw data below
    st.subheader("Raw Event Data")
    st.dataframe(match_df)
