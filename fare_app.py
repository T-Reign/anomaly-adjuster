import streamlit as st
import pandas as pd
import math
import os
from collections import defaultdict
import plotly.graph_objects as go

st.set_page_config(page_title="Anomaly Adjuster", layout="wide")

# --- CACHE THE CSV CONVERSION ---\n@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# --- HEADER ---
col_logo, col_text = st.columns([1, 5])
with col_logo:
    logo_path = "SWR_Logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=120)
    else:
        st.info("Logo Placeholder")

with col_text:
    st.title("Anomaly Adjuster")
    st.caption("Prototype adjuster for Oval fares (part 2)")

# --- 1. SEQUENCES ---
SEQUENCES = {
    "Wanborough Main Line": ["ASH", "WANBOROUGH", "GUILDFORD", "WORPLESDON", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Alton Main Line": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"]
}

# --- 2. DATA LOAD ---
@st.cache_data
def load_raw_data():
    main_file = "Bagshot Fares for Python.xlsx - Main Sheet.csv"
    jr_file = "Bagshot Fares for Python.xlsx - Journeys and Revenue.csv"
    
    if not os.path.exists(main_file) or not os.path.exists(jr_file):
        return None, None
        
    df_main = pd.read_csv(main_file)
    df_jr = pd.read_csv(jr_file)
    return df_main, df_jr

df_main_raw, df_jr_raw = load_raw_data()

if df_main_raw is None or df_jr_raw is None:
    st.error("Missing required CSV files. Please check paths.")
    st.stop()

# Clean up string text columns
for c in ['Origin Description', 'Destination Description']:
    if c in df_main_raw.columns:
        df_main_raw[c] = df_main_raw[c].astype(str).str.strip().str.upper()

for c in ['True Origin Description', 'True Destination Description', 'Fare Product Group Description', 'Product Ticket Type']:
    if c in df_jr_raw.columns:
        df_jr_raw[c] = df_jr_raw[c].astype(str).str.strip().str.upper()

# --- 3. SIDEBAR CONTROLS ---
st.sidebar.header("Geography & Ticket Selection")

chosen_seq_name = st.sidebar.selectbox("Select Station Milestone Corridor Line:", list(SEQUENCES.keys()))
route_stations = SEQUENCES[chosen_seq_name]

start_stn = st.sidebar.selectbox("Select Outward Point of Origin:", route_stations[:-1])
start_idx = route_stations.index(start_stn)
possible_dests = route_stations[start_idx+1:]

ticket_options = {
    "SDS": "Anytime Day Single (SDS)",
    "SDR": "Anytime Day Return (SDR)",
    "CDS": "Off-Peak Day Single (CDS)",
    "CDR": "Off-Peak Day Return (CDR)",
    "7DS": "7 Day Season (7DS)"
}
chosen_ticket = st.sidebar.selectbox("Select Ticket Type Category to Adjust:", list(ticket_options.keys()), format_func=lambda x: ticket_options[x])

st.sidebar.subheader("Elasticity Scaling Parameter")
elasticity_value = st.sidebar.slider("Price Elasticity Factor (Beta Group):", -2.5, 0.0, -0.8, step=0.1)

st.sidebar.subheader("Progression Boundary Caps")
cap_sds = st.sidebar.slider("Max % Jump per Stop (SDS)", 1.05, 1.50, 1.25, step=0.01)
cap_sdr = st.sidebar.slider("Max % Jump per Stop (SDR)", 1.05, 1.50, 1.25, step=0.01)
cap_cds = st.sidebar.slider("Max % Jump per Stop (CDS)", 1.05, 1.50, 1.25, step=0.01)
cap_cdr = st.sidebar.slider("Max % Jump per Stop (CDR)", 1.05, 1.50, 1.25, step=0.01)
cap_7ds = st.sidebar.slider("Max % Jump per Stop (7DS)", 1.05, 1.50, 1.25, step=0.01)

BOUNDARIES = {"SDS": cap_sds, "SDR": cap_sdr, "CDS": cap_cds, "CDR": cap_cdr, "7DS": cap_7ds}

# --- 4. STEPPING LOOP GRAPH GENERATOR LOGIC ---
milestones_found = []
for d in possible_dests:
    match = df_main_raw[(df_main_raw['Origin Description'] == start_stn) & (df_main_raw['Destination Description'] == d)]
    if not match.empty:
        milestones_found.append(d)

if not milestones_found:
    st.warning(f"No milestone data rows found matching '{start_stn}' going down the sequence chain.")
    st.stop()

# Extract and build vectors
base_sds_arr = []
base_sdr_arr = []
base_cds_arr = []
base_cdr_arr = []
base_7ds_arr = []

old_sop_arr = []

for d in milestones_found:
    row = df_main_raw[(df_main_raw['Origin Description'] == start_stn) & (df_main_raw['Destination Description'] == d)].iloc[0]
    base_sds_arr.append(float(row['SDS']) if 'SDS' in row and pd.notna(row['SDS']) else 0.0)
    base_sdr_arr.append(float(row['SDR']) if 'SDR' in row and pd.notna(row['SDR']) else 0.0)
    base_cds_arr.append(float(row['CDS']) if 'CDS' in row and pd.notna(row['CDS']) else 0.0)
    base_cdr_arr.append(float(row['CDR']) if 'CDR' in row and pd.notna(row['CDR']) else 0.0)
    base_7ds_arr.append(float(row['7DS']) if '7DS' in row and pd.notna(row['7DS']) else 0.0)
    
    # Track reference points if they exist
    val_sop = 0.0
    if 'EVA' in row and pd.notna(row['EVA']) and float(row['EVA']) > 0: val_sop = float(row['EVA'])
    elif 'SUA' in row and pd.notna(row['SUA']) and float(row['SUA']) > 0: val_sop = float(row['SUA'])
    elif 'EVB' in row and pd.notna(row['EVB']) and float(row['EVB']) > 0: val_sop = float(row['EVB'])
    elif 'SUB' in row and pd.notna(row['SUB']) and float(row['SUB']) > 0: val_sop = float(row['SUB'])
    old_sop_arr.append(val_sop if val_sop > 0 else None)

# OPTIMIZATION PASS
N = len(milestones_found)
new_sds = list(base_sds_arr)
new_sdr = list(base_sdr_arr)
new_cds = list(base_cds_arr)
new_cdr = list(base_cdr_arr)
new_7ds = list(base_7ds_arr)

# Forward pass boundaries logic
for i in range(1, N):
    if new_sds[i] < new_sds[i-1]: new_sds[i] = new_sds[i-1]
    if new_sds[i] > new_sds[i-1] * BOUNDARIES["SDS"]: new_sds[i] = new_sds[i-1] * BOUNDARIES["SDS"]
    
    if new_sdr[i] < new_sdr[i-1]: new_sdr[i] = new_sdr[i-1]
    if new_sdr[i] > new_sdr[i-1] * BOUNDARIES["SDR"]: new_sdr[i] = new_sdr[i-1] * BOUNDARIES["SDR"]
    
    if new_cds[i] < new_cds[i-1]: new_cds[i] = new_cds[i-1]
    if new_cds[i] > new_cds[i-1] * BOUNDARIES["CDS"]: new_cds[i] = new_cds[i-1] * BOUNDARIES["CDS"]
    
    if new_cdr[i] < new_cdr[i-1]: new_cdr[i] = new_cdr[i-1]
    if new_cdr[i] > new_cdr[i-1] * BOUNDARIES["CDR"]: new_cdr[i] = new_cdr[i-1] * BOUNDARIES["CDR"]
    
    if new_7ds[i] < new_7ds[i-1]: new_7ds[i] = new_7ds[i-1]
    if new_7ds[i] > new_7ds[i-1] * BOUNDARIES["7DS"]: new_7ds[i] = new_7ds[i-1] * BOUNDARIES["7DS"]

# Relational cross-rule boundaries capping checks
for i in range(N):
    if new_sdr[i] < new_sds[i]: new_sdr[i] = new_sds[i]
    if new_cdr[i] < new_cds[i]: new_cdr[i] = new_cds[i]
    if new_cds[i] > new_sds[i]: new_cds[i] = new_sds[i]
    if new_cdr[i] > new_sdr[i]: new_cdr[i] = new_sdr[i]

# Map vectors back into a dictionary for evaluation mapping
optimized_fares = {}
for idx, d in enumerate(milestones_found):
    optimized_fares[d] = {
        "SDS": new_sds[idx], "SDR": new_sdr[idx],
        "CDS": new_cds[idx], "CDR": new_cdr[idx],
        "7DS": new_7ds[idx]
    }

# --- 5. REVENUE & JOURNEY EVALUATION PIPELINE ---
# Filter global volume rows
df_jr = df_jr_raw[
    (df_jr_raw['True Origin Description'] == start_stn) & 
    (df_jr_raw['True Destination Description'].isin(milestones_found))
].copy()

# Map product names cleanly
def get_mapped_type(row):
    g_desc = str(row['Fare Product Group Description'])
    t_desc = str(row['Product Ticket Type'])
    p_code = str(row['Product Code']).upper()
    
    if "7 DAY" in g_desc or "SEASON" in g_desc or p_code == "7DS": return "7DS"
    if "SUPER OFF-PEAK" in g_desc or "SOP" in t_desc:
        if "SINGLE" in t_desc or "SSS" in p_code: return "CDS"
        return "CDR"
    if "OFF-PEAK" in g_desc:
        if "SINGLE" in t_desc or "CDS" in p_code: return "CDS"
        return "CDR"
    if "ANYTIME" in g_desc or "PEAK" in g_desc:
        if "SINGLE" in t_desc or "SDS" in p_code: return "SDS"
        return "SDR"
    return "CDR"

if not df_jr.empty:
    df_jr['Derived_Type'] = df_jr.apply(get_mapped_type, axis=1)
    df_jr = df_jr[df_jr['Derived_Type'] == chosen_ticket].copy()

# Aggregate volumes to a flow structure level
flow_data = []
for d in milestones_found:
    sub = df_jr[df_jr['True Destination Description'] == d]
    tot_j = float(sub['JOURNEYS'].sum()) if not sub.empty else 0.0
    tot_r = float(sub['REVENUE'].sum()) if not sub.empty else 0.0
    
    # Pull master reference numbers
    m_row = df_main_raw[(df_main_raw['Origin Description'] == start_stn) & (df_main_raw['Destination Description'] == d)].iloc[0]
    orig_fare = float(m_row[chosen_ticket]) if chosen_ticket in m_row and pd.notna(m_row[chosen_ticket]) else 0.0
    new_fare = optimized_fares[d][chosen_ticket]
    
    # Calculate price difference
    diff = new_fare - orig_fare
    pct_change = (diff / orig_fare) if orig_fare > 0 else 0.0
    
    # Apply elasticity factor formula
    pred_j = tot_j * (1.0 + (elasticity_value * pct_change)) if orig_fare > 0 else tot_j
    if pred_j < 0: pred_j = 0.0
    
    old_ticket_rev = tot_j * orig_fare
    new_ticket_rev = pred_j * new_fare
    rev_impact = new_ticket_rev - old_ticket_rev
    
    flow_data.append({
        "Origin Description": start_stn,
        "Destination Description": d,
        "Filtered_Journeys": tot_j,
        "Original_SDR": float(m_row['SDR']) if 'SDR' in m_row and pd.notna(m_row['SDR']) else 0.0,
        "New_SDR": optimized_fares[d]['SDR'],
        "Display_Original_Fare": orig_fare,
        "Display_New_Fare": new_fare,
        "Diff": diff,
        "Predicted_Journeys": pred_j,
        "Old_Ticket_Revenue": old_ticket_rev,
        "New_Ticket_Revenue": new_ticket_rev,
        "Revenue_Impact": rev_impact,
        "Abs_Revenue_Impact": abs(rev_impact),
        "Status": "Optimized" if abs(diff) > 0.01 else "Unchanged"
    })

df = pd.DataFrame(flow_data)

# --- 6. SPLIT TICKETING & ANOMALY LOOKUP CRUNCHER ---
split_records = []
long_buy_records = []

# Fetch active baseline dictionary for splits evaluation
current_fares_dict = {}
for d in milestones_found:
    row_m = df_main_raw[(df_main_raw['Origin Description'] == start_stn) & (df_main_raw['Destination Description'] == d)].iloc[0]
    current_fares_dict[d] = float(row_m[chosen_ticket]) if chosen_ticket in row_m and pd.notna(row_m[chosen_ticket]) else 0.0

for idx, d in enumerate(milestones_found):
    actual_fare = current_fares_dict[d]
    if actual_fare <= 0: continue
    
    # A. Split Ticketing Check
    for split_idx in range(idx):
        mid_stn = milestones_found[split_idx]
        
        # Query the leg from start to mid-station
        leg1_fare = current_fares_dict[mid_stn]
        
        # Query the leg from mid-station to destination
        leg2_match = df_main_raw[(df_main_raw['Origin Description'] == mid_stn) & (df_main_raw['Destination Description'] == d)]
        if not leg2_match.empty:
            leg2_row = leg2_match.iloc[0]
            leg2_fare = float(leg2_row[chosen_ticket]) if chosen_ticket in leg2_row and pd.notna(leg2_row[chosen_ticket]) else 0.0
            
            if leg1_fare > 0 and leg2_fare > 0:
                combined = leg1_fare + leg2_fare
                if combined < actual_fare:
                    split_records.append({
                        "True Destination": d,
                        "Through Fare": actual_fare,
                        "Split Stop Station": mid_stn,
                        "Leg 1 Price": leg1_fare,
                        "Leg 2 Price": leg2_fare,
                        "Combined Split Price": combined,
                        "Anomalous Loophole Saving": actual_fare - combined
                    })
                    
    # B. Long-Buying Check
    for further_idx in range(idx + 1, len(milestones_found)):
        further_stn = milestones_found[further_idx]
        further_fare = current_fares_dict[further_stn]
        
        if further_fare > 0 and further_fare < actual_fare:
            long_buy_records.append({
                "Intended Destination": d,
                "Intended Price": actual_fare,
                "Cheaper Ticket Beyond": further_stn,
                "Price Beyond": further_fare,
                "Loopholes Arbitrage Margin": actual_fare - further_fare
            })

df_splits = pd.DataFrame(split_records)
df_long = pd.DataFrame(long_buy_records)

# =========================================================================
# 🗂️ CREATING THE MAIN NAVIGATION TABS (THE SLIDES)
# =========================================================================
tab_analytics, tab_splits = st.tabs(["📊 Revenue & Journey Analytics", "🔍 Split Ticketing & Anomalies"])

# =========================================================================
# SLIDE 1: REVENUE & JOURNEY ANALYTICS
# =========================================================================
with tab_analytics:

    # --- ROW 1 & 2: PLOTS GRAPH CONTROLLERS ---
    gc1, gc2 = st.columns(2)

    with gc1:
        fig_prog = go.Figure()
        fig_prog.add_trace(go.Scatter(
            x=df["Destination Description"], y=df["Display_Original_Fare"], mode="lines+markers",
            name="Original Baseline", line=dict(color="blue", width=2), marker=dict(size=6)
        ))
        fig_prog.add_trace(go.Scatter(
            x=df["Destination Description"], y=df["Display_New_Fare"], mode="lines+markers",
            name="Smoothed Boundaries Outward", line=dict(color="red", width=3), marker=dict(size=8)
        ))
        fig_prog.update_layout(
            title=f"Fare Stepping Curves Profile: Outward from {start_stn.title()}",
            xaxis_title="Milestone Stop Target", yaxis_title="Price Point Value (£)",
            template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_prog, use_container_width=True)

    with gc2:
        chart_data_comparison = []
        for idx, d in enumerate(milestones_found):
            chart_data_comparison.append({
                "Station": d,
                "Old Fare (£)": base_sdr_arr[idx] if chosen_ticket in ["SDR","CDR","7DS"] else base_sds_arr[idx],
                "Old Super Off-Peak (£)": old_sop_arr[idx],
                "New Fare (£)": optimized_fares[d][chosen_ticket],
                "Change (£)": df.iloc[idx]["Diff"] if idx < len(df) else 0.0
            })
            
        if chart_data_comparison:
            df_comp = pd.DataFrame(chart_data_comparison)
            
            # 1. NEW STRIP: Build a pre-formatted string with the sign on the outside of the symbol
            df_comp["Variance_Text"] = df_comp["Change (£)"].apply(
                lambda x: f"+£{x:.2f}" if x > 0 else f"-£{abs(x):.2f}" if x < 0 else "£0.00" if pd.notna(x) else ""
            )
            
            fig_comp = go.Figure()
            
            # SMART FIX: Only plot the blue line if there is at least one non-zero historical fare on this route segment
            if df_comp["Old Fare (£)"].notna().any():
                fig_comp.add_trace(go.Scatter(
                    x=df_comp["Station"], y=df_comp["Old Fare (£)"], mode="lines+markers",
                    name="Fares Today", line=dict(color="#1f77b4", width=3), marker=dict(size=8),
                    connectgaps=True, # If a random station in the middle is 0, it neatly connects the rest
                    hovertemplate="<b>To: %{x}</b><br>Fares Today: £%{y:.2f}<extra></extra>"
                ))
            
            # Orange Dotted Line: Super Off-Peak Reference
            if chosen_ticket in ["CDR", "CDS"] and df_comp["Old Super Off-Peak (£)"].notna().any():
                fig_comp.add_trace(go.Scatter(
                    x=df_comp["Station"], y=df_comp["Old Super Off-Peak (£)"], mode="lines+markers",
                    name="Old Super Off-Peak (Withdrawn)", line=dict(color="orange", width=2, dash="dot"), marker=dict(size=6),
                    hovertemplate="<b>To: %{x}</b><br>Withdrawn SOP Fare: £%{y:.2f}<extra></extra>"
                ))
            
            # Red Line: New Optimized Fares
            fig_comp.add_trace(go.Scatter(
                x=df_comp["Station"], y=df_comp["New Fare (£)"], mode="lines+markers",
                name=f"New Optimized {chosen_ticket}", line=dict(color="#d62728", width=3), marker=dict(size=8),
                customdata=df_comp["Variance_Text"], # 2. UPDATED: Points to our newly formatted text field
                hovertemplate="<b>To: %{x}</b><br>New Fare: £%{y:.2f}<br>True Variance: %{customdata}<extra></extra>" if df_comp["Change (£)"].notna().any() else "<b>To: %{x}</b><br>New Fare: £%{y:.2f}<extra></extra>" # 3. UPDATED: Simplified clean token string display
            ))
            
            fig_comp.update_layout(
                title=f"{chosen_ticket} Progression Outward from {start_stn.title()}",
                xaxis_title="Destination Milestone Stops", yaxis_title="Fare Price (£)",
                template="plotly_white", 
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified"
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info("No historical comparison data rows found for this selection.")

    # --- ROW 3: JOURNEY & REVENUE IMPACT TABLES ---
    st.divider()
    r3c1, r3c2 = st.columns(2)
    with r3c1:
        st.subheader("Biggest Journey Volume Changes")
        st.caption(f"Flows with price steps affecting highest volume of **{chosen_ticket}** journeys")
        
        # Slice and make a copy to add our cleanly formatted text column
        journey_changes = df[df['Diff'].abs() > 0.01].sort_values('Filtered_Journeys', ascending=False).head(10).copy()
        journey_changes['Price_Change_Text'] = journey_changes['Diff'].apply(
            lambda x: f"+£{x:.2f}" if x > 0 else f"-£{abs(x):.2f}" if x < 0 else "£0.00" if pd.notna(x) else ""
        )
        
        st.dataframe(journey_changes[['Origin Description', 'Destination Description', 'Filtered_Journeys', 'Display_Original_Fare', 'Display_New_Fare', 'Price_Change_Text']], 
                     column_config={
                         "Filtered_Journeys": st.column_config.NumberColumn("Journeys Affected", format="%,d"), 
                         "Display_Original_Fare": st.column_config.NumberColumn("Original Fare", format="£%.2f"), 
                         "Display_New_Fare": st.column_config.NumberColumn("New Fare", format="£%.2f"), 
                         "Price_Change_Text": st.column_config.TextColumn("Price Change")
                     }, use_container_width=True, hide_index=True)
        
        st.write("") 
        m1, m2 = st.columns(2)
        total_prev_journeys = df['Filtered_Journeys'].sum()
        total_new_journeys = df['Predicted_Journeys'].sum()
        journey_delta = total_new_journeys - total_prev_journeys
        
        m1.metric(label=f"Previous {chosen_ticket} Journeys", value=f"{total_prev_journeys:,.0f}")
        m2.metric(label=f"New Predicted {chosen_ticket} Journeys", value=f"{total_new_journeys:,.0f}", delta=f"{journey_delta:+,.0f}")
                     
    with r3c2:
        st.subheader("Biggest Financial Revenue Impacts")
        st.caption(f"Flows with the largest currency variance ({chosen_ticket} Segment Volume × Delta)")
        
        # Slice and make a copy to add clean currency text columns
        revenue_changes = df.sort_values('Abs_Revenue_Impact', ascending=False).head(10).copy()
        revenue_changes['Price_Change_Text'] = revenue_changes['Diff'].apply(
            lambda x: f"+£{x:.2f}" if x > 0 else f"-£{abs(x):.2f}" if x < 0 else "£0.00" if pd.notna(x) else ""
        )
        revenue_changes['Revenue_Impact_Text'] = revenue_changes['Revenue_Impact'].apply(
            lambda x: f"+£{x:,.0f}" if x > 0 else f"-£{abs(x):,.0f}" if x < 0 else "£0" if pd.notna(x) else ""
        )
        
        st.dataframe(revenue_changes[['Origin Description', 'Destination Description', 'Filtered_Journeys', 'Price_Change_Text', 'Revenue_Impact_Text']], 
                     column_config={
                         "Filtered_Journeys": st.column_config.NumberColumn("Ticket Volume", format="%,d"), 
                         "Price_Change_Text": st.column_config.TextColumn("Price Change"), 
                         "Revenue_Impact_Text": st.column_config.TextColumn("Revenue Impact")
                     }, use_container_width=True, hide_index=True)
        
        st.write("") 
        m3, m4 = st.columns(2)
        total_prev_rev = df['Old_Ticket_Revenue'].sum()
        total_new_rev = df['New_Ticket_Revenue'].sum()
        revenue_delta = total_new_rev - total_prev_rev
        
        # Pre-format the delta metric to keep the minus sign cleanly on the outside
        revenue_delta_str = f"+£{revenue_delta:,.0f}" if revenue_delta > 0 else f"-£{abs(revenue_delta):,.0f}" if revenue_delta < 0 else "£0"
        
        m3.metric(label=f"Previous {chosen_ticket} Yield", value=f"£{total_prev_rev:,.0f}")
        m4.metric(label=f"New Predicted {chosen_ticket} Yield", value=f"£{total_new_rev:,.0f}", delta=revenue_delta_str)


# =========================================================================
# SLIDE 2: SPLIT TICKETING & LONG-BUYING ANOMALIES
# =========================================================================
with tab_splits:
    st.subheader("Split Ticketing Opportunities / Existing Loophole Violations")
    st.caption("Flows where buying two ticketing segments sequentially is cheaper than buying one through ticket.")
    if not df_splits.empty:
        # Pre-format the negative/saving variables out-of-box to maintain proper layout styles
        df_splits_disp = df_splits.copy()
        df_splits_disp["Anomalous Loophole Saving"] = df_splits_disp["Anomalous Loophole Saving"].apply(lambda x: f"£{x:.2f}")
        st.dataframe(df_splits_disp, column_config={
            "Through Fare": st.column_config.NumberColumn("Through Price", format="£%.2f"),
            "Leg 1 Price": st.column_config.NumberColumn("Leg 1", format="£%.2f"),
            "Leg 2 Price": st.column_config.NumberColumn("Leg 2", format="£%.2f"),
            "Combined Split Price": st.column_config.NumberColumn("Combined Leg Sum", format="£%.2f"),
            "Anomalous Loophole Saving": st.column_config.TextColumn("Customer Savings")
        }, use_container_width=True, hide_index=True)
    else:
        st.success("Excellent! No split-ticketing anomalies or pricing defects found along this path segment sequence.")
        
    st.write("")
    st.subheader("Long-Buying / Beyond-Station Target Market Arbitrage Anomalies")
    st.caption("Flows where purchasing a ticket to a further station down the line costs less than stopping at the true destination milestone.")
    if not df_long.empty:
        df_long_disp = df_long.copy()
        df_long_disp["Loopholes Arbitrage Margin"] = df_long_disp["Loopholes Arbitrage Margin"].apply(lambda x: f"£{x:.2f}")
        st.dataframe(df_long_disp, column_config={
            "Intended Price": st.column_config.NumberColumn("Intended Price", format="£%.2f"),
            "Price Beyond": st.column_config.NumberColumn("Price Beyond", format="£%.2f"),
            "Loopholes Arbitrage Margin": st.column_config.TextColumn("Arbitrage Profit Delta Margin")
        }, use_container_width=True, hide_index=True)
    else:
        st.success("Excellent! No long-buying pricing loopholes or sequence step defects found along this segment line.")


# =========================================================================
# GLOBAL FOOTER AREA (VISSBLE ACROSS ALL TABS)
# =========================================================================
st.divider()
st.subheader("Full Context Fare Summary")

output_df = df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Display_Original_Fare', 'Display_New_Fare', 'Status']].copy()
st.dataframe(output_df, column_config={
    "Original_SDR": st.column_config.NumberColumn("Base Orig SDR", format="£%.2f"), 
    "New_SDR": st.column_config.NumberColumn("Base New SDR", format="£%.2f"),
    "Display_Original_Fare": st.column_config.NumberColumn(f"Orig {chosen_ticket}", format="£%.2f"),
    "Display_New_Fare": st.column_config.NumberColumn(f"New {chosen_ticket}", format="£%.2f")
}, use_container_width=True, hide_index=True)

# --- EXPORT TO CSV BUTTONS ---
csv_data = convert_df_to_csv(df)
st.download_button(
    label="📥 Export Optimized Matrix Results (CSV)",
    data=csv_data,
    file_name=f"optimized_fares_{start_stn}_{chosen_ticket}.csv",
    mime="text/csv"
)
