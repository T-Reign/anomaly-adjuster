import streamlit as st
import pandas as pd
import math
import os
from collections import defaultdict

st.set_page_config(page_title="Anomaly Adjuster", layout="wide")

# --- CACHE THE CSV CONVERSION ---
@st.cache_data
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
    "Reading-Alton": ["READING", "EARLEY", "WINNERSH TRIANGLE", "WINNERSH", "WOKINGHAM", "BRACKNELL", "MARTINS HERON", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "FARNHAM", "BENTLEY", "ALTON"],
    "Reading-Guilford": ["READING", "EARLEY", "WINNERSH TRIANGLE", "WINNERSH", "WOKINGHAM", "BRACKNELL", "MARTINS HERON", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD"],
    "Bagshot-Ashtead": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "ASHTEAD"],
    "Alton-Ashtead": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "ASHTEAD"],
    "Bagshot-Dorking": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "BOX HILL & WESTHUMBLE", "DORKING"],
    "Alton-Dorking": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "BOX HILL & WESTHUMBLE", "DORKING"],
    "Via Surbiton": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "HINCHLEY WOOD", "CLAYGATE", "OXSHOTT"],
    "Via Walton-On-Thames": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "HINCHLEY WOOD", "CLAYGATE", "OXSHOTT"],
    "Via Ascot": ["ZONE R1256 LONDON", "LONDON BR", "QUEENSTOWN ROAD(BATTERSEA)", "CLAPHAM JUNCTION LONDON", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "FARNHAM", "BENTLEY", "ALTON"],
    "Wanborough Main Line": ["ASH", "WANBOROUGH", "GUILDFORD", "WORPLESDON", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Alton Main Line": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Via Woking": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Via Guildford": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "COBHAM & STOKE D'ABERNON", "OXSHOTT", "CLAYGATE", "HINCHLEY WOOD"],
    "Via Clandon": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "COBHAM & STOKE D'ABERNON", "OXSHOTT", "CLAYGATE", "HINCHLEY WOOD"],
    "Brookwood-Wanborough": ["BROOKWOOD", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH"],
    "Via Virginia Water": ["ADDLESTONE", "CHERTSEY", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "FARNHAM", "BENTLEY", "ALTON"],
    "Via Longcross": ["ADDLESTONE", "CHERTSEY", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH"],
    "Via Weybridge": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "ADDLESTONE", "CHERTSEY"],
    "Via Brookwood": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "ADDLESTONE", "CHERTSEY"],
    "Via West Byfleet": ["ASH", "WANBOROUGH", "GUILDFORD", "WORPLESDON", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "ADDLESTONE", "CHERTSEY"]
}

def round_up(x, base):
    if pd.isna(x) or x <= 0: return 0.0
    if base < 0.01: return round(float(x), 2)
    multiplied = round(float(x), 2) * (1/base)
    rounded_up = math.ceil(round(multiplied, 7)) / (1/base)
    return round(rounded_up, 2)

# --- 2. SIDEBAR ---
st.sidebar.header("1. Split-Ticket Exclusions")
raw_split_ex = st.sidebar.text_area("Flows to exclude from split adjustment:", value="Reading-Earley")
excluded_splits = {line.strip().upper().replace(" ", "") for line in raw_split_ex.split('\n') if "-" in line}

st.sidebar.header("2. Long-Buy Exclusions")
raw_lb_ex = st.sidebar.text_area("Flows to exclude from long-buy adjustment:", value="Aldershot-Oxshott")
excluded_longbuys = {line.strip().upper().replace(" ", "") for line in raw_lb_ex.split('\n') if "-" in line}

st.sidebar.header("3. Optimisation Settings")
slp_enabled = st.sidebar.checkbox("Enable Single-Leg Pricing", value=True)
sdr_rounding = st.sidebar.select_slider("Rounding (£)", options=[0.00, 0.05, 0.10, 0.20, 0.50, 1.00], value=0.20)
inc_cap = st.sidebar.slider("Maximum Increase (cap) (%)", 0, 70, 8) / 100
dec_cap = st.sidebar.slider("Maximum Decrease (cap) (%)", 0, 70, 5) / 100

st.sidebar.markdown("---")
st.sidebar.subheader("Low-Volume Adjustments")
enable_low_vol = st.sidebar.checkbox("Enable Low-Volume Rules", value=True)
low_vol_threshold = st.sidebar.number_input("Low Volume Threshold (Journeys)", value=1000, step=100)
low_vol_action = st.sidebar.radio("Action for low-volume flows:", ["Double the Cap", "Ignore the Cap Completely"])

st.sidebar.markdown("---")
st.sidebar.subheader("Revenue Protection Guardrails")
enable_high_rev = st.sidebar.checkbox("Enable Revenue Protection", value=True)
high_rev_threshold = st.sidebar.number_input("High Revenue Threshold (£)", value=30000, step=5000)
high_rev_action = st.sidebar.radio("Action for high-revenue flows:", ["Halve the Decrease Cap", "Do Not Decrease At All"])
sdr_elasticity = st.sidebar.slider("SDR Demand Elasticity", -2.0, 0.0, -0.6, step=0.05)

uploaded_files = st.sidebar.file_uploader("Upload Fare Spreadsheets", type=["xlsx"], accept_multiple_files=True)

# --- 3. PROCESSING ---
if uploaded_files:
    with st.spinner("Calculating Optimised Network & Merging Revenue..."):
        all_dfs = []
        all_jr_dfs = []
        
        for f in uploaded_files:
            df_main = pd.read_excel(f, sheet_name='Main Sheet', header=1)
            all_dfs.append(df_main)
            
            try:
                df_jr_raw = pd.read_excel(f, sheet_name='Journeys and Revenue')
                all_jr_dfs.append(df_jr_raw)
            except Exception as e:
                st.error(f"Could not find 'Journeys and Revenue' sheet in {f.name}. Please ensure the sheet name matches exactly.")

        df = pd.concat(all_dfs, ignore_index=True)
        df.columns = [str(c).strip() for c in df.columns]
        
        df['Origin Description'] = df.iloc[:, 1].astype(str).str.strip().str.title()
        df['Destination Description'] = df.iloc[:, 3].astype(str).str.strip().str.title()
        
        df['Origin_N'] = df['Origin Description'].str.upper().str.replace(" ", "")
        df['Dest_N'] = df['Destination Description'].str.upper().str.replace(" ", "")
        df['Match_ID'] = df['Origin_N'] + "-" + df['Dest_N']
        
        df['Original_SDR'] = pd.to_numeric(df.iloc[:, 9], errors='coerce').fillna(0.0)
        df = df.sort_values('Original_SDR', ascending=False).drop_duplicates(subset=['Match_ID']).copy()
        
        raw_price_map = df.set_index('Match_ID')['Original_SDR'].to_dict()

        if all_jr_dfs:
            df_jr = pd.concat(all_jr_dfs, ignore_index=True)
            df_jr.columns = [str(c).strip() for c in df_jr.columns]
            
            df_jr['Origin_N'] = df_jr['True Origin Description'].astype(str).str.upper().str.replace(" ", "")
            df_jr['Dest_N'] = df_jr['True Destination Description'].astype(str).str.upper().str.replace(" ", "")
            df_jr['Match_ID'] = df_jr['Origin_N'] + "-" + df_jr['Dest_N']
            
            product_mapping = {
                '2BAF': 'SDR', '1BAF': 'SDR',
                '2AAA': 'SDS', '1AAA': 'SDS',
                '2ADA': 'CDS', 'ADA': 'CDS',
                '2BDY': 'CDR',
                '2MQA': '7DF', '1MQA': '7DF',
                '2BHA': 'CDR', '2HYV': 'CDR',
                '2ADO': 'CDS', '2HYU': 'CDS'
            }
            
            df_jr['Product_Clean'] = df_jr['Product Code'].astype(str).str.strip().str.upper()
            df_jr['Standard_Product'] = df_jr['Product_Clean'].map(product_mapping)
            
            df_jr['JOURNEYS'] = pd.to_numeric(df_jr['JOURNEYS'], errors='coerce').fillna(0)
            df_jr['REVENUE'] = pd.to_numeric(df_jr['REVENUE'], errors='coerce').fillna(0.0)
            
            total_jr_summary = df_jr.groupby('Match_ID')['JOURNEYS'].sum().reset_index()
            total_jr_summary.columns = ['Match_ID', 'Total_Journeys']
            
            df_sdr_jr = df_jr[df_jr['Standard_Product'] == 'SDR']
            sdr_jr_summary = df_sdr_jr.groupby('Match_ID').agg({
                'JOURNEYS': 'sum',
                'REVENUE': 'sum'
            }).reset_index()
            sdr_jr_summary.columns = ['Match_ID', 'SDR_Journeys', 'SDR_Revenue']
            
            df = df.merge(total_jr_summary, on='Match_ID', how='left')
            df = df.merge(sdr_jr_summary, on='Match_ID', how='left')
            
            df['Total_Journeys'] = df['Total_Journeys'].fillna(0)
            df['SDR_Journeys'] = df['SDR_Journeys'].fillna(0)
            df['SDR_Revenue'] = df['SDR_Revenue'].fillna(0.0)
        else:
            df['Total_Journeys'] = 0
            df['SDR_Journeys'] = 0
            df['SDR_Revenue'] = 0.0
        
        def initial_prep(row):
            parts = row['Match_ID'].split("-")
            rev_id = f"{parts[1]}-{parts[0]}"
            highest = max(row['Original_SDR'], raw_price_map.get(rev_id, 0))
            val = highest if slp_enabled else row['Original_SDR']
            return round_up(val, sdr_rounding)

        df['New_SDR'] = df.apply(initial_prep, axis=1)
        df['Base_Price'] = df['New_SDR'].copy()

        def calculate_ceiling(row):
            if enable_low_vol and (row['Total_Journeys'] < low_vol_threshold):
                if low_vol_action == "Ignore the Cap Completely":
                    return 9999.0
                else:
                    effective_cap = inc_cap * 2
            else:
                effective_cap = inc_cap
                
            raw_ceiling = row['Original_SDR'] * (1 + effective_cap)
            return round_up(raw_ceiling, sdr_rounding)

        df['Ceiling_Price'] = df.apply(calculate_ceiling, axis=1)

        def calculate_floor(row):
            if enable_high_rev and (row['SDR_Revenue'] > high_rev_threshold):
                if high_rev_action == "Do Not Decrease At All":
                    return row['Original_SDR']
                else:
                    effective_dec_cap = dec_cap / 2
            else:
                effective_dec_cap = dec_cap
                
            raw_floor = row['Original_SDR'] * (1 - effective_dec_cap)
            return round_up(raw_floor, sdr_rounding)

        df['Floor_Price'] = df.apply(calculate_floor, axis=1)

        adj = defaultdict(list)
        for mid in raw_price_map.keys():
            o, d = mid.split("-")
            adj[o].append(d)

        for _ in range(2):
            curr = df.set_index('Match_ID')['New_SDR'].to_dict()
            for A in adj:
                for B in adj[A]:
                    if B not in adj: continue
                    for C in adj[B]:
                        id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                        if id_ac in curr:
                            thru, s_sum = curr[id_ac], curr[id_ab] + curr.get(id_bc, 9999)
                            if s_sum < (thru - 0.009):
                                if id_bc in curr and id_bc not in excluded_splits:
                                    pot_inc = round_up(curr[id_bc] + (thru - s_sum)/2, sdr_rounding)
                                    curr[id_bc] = min(pot_inc, df.loc[df['Match_ID']==id_bc, 'Ceiling_Price'].values[0])
                                if id_ac not in excluded_splits:
                                    pot_dec = round_up(curr[id_ab] + curr[id_bc], sdr_rounding)
                                    curr[id_ac] = max(pot_dec, df.loc[df['Match_ID']==id_ac, 'Floor_Price'].values[0])
            
            for path in SEQUENCES.values():
                for i, s in enumerate(path):
                    s_c = s.replace(" ","")
                    for j, n in enumerate(path[i+1:], i+1):
                        n_c = n.replace(" ","")
                        for k, f in enumerate(path[j+1:], j+1):
                            f_c = f.replace(" ","")
                            id_near, id_far = f"{s_c}-{n_c}", f"{s_c}-{f_c}"
                            if id_near in curr and id_far in curr:
                                if curr[id_near] > curr[id_far] and id_near not in excluded_longbuys:
                                    curr[id_near] = max(curr[id_far], df.loc[df['Match_ID']==id_near, 'Floor_Price'].values[0])
        df['New_SDR'] = df['Match_ID'].map(curr)

        if slp_enabled:
            final_prices = df.set_index('Match_ID')['New_SDR'].to_dict()
            for mid in list(final_prices.keys()):
                o, d = mid.split("-")
                rev = f"{d}-{o}"
                if rev in final_prices:
                    unified = max(final_prices[mid], final_prices[rev])
                    c1, f1 = df.loc[df['Match_ID']==mid, ['Ceiling_Price','Floor_Price']].values[0]
                    c2, f2 = df.loc[df['Match_ID']==rev, ['Ceiling_Price','Floor_Price']].values[0]
                    final_val = min(max(unified, min(f1, f2)), max(c1, c2))
                    final_prices[mid] = final_prices[rev] = round_up(final_val, sdr_rounding)
            df['New_SDR'] = df['Match_ID'].map(final_prices)

        df['Diff'] = df['New_SDR'] - df['Original_SDR']
        df['Opt_Increase'] = df['New_SDR'] - df['Base_Price']
        df['Status'] = df['Diff'].apply(lambda x: "Increased" if x > 0.01 else ("Decreased" if x < -0.01 else "Unchanged"))
        
        safe_orig_fare = df['Original_SDR'].replace(0, 1)
        df['Price_Pct_Change'] = df['Diff'] / safe_orig_fare
        
        df['Predicted_SDR_Journeys'] = df['SDR_Journeys'] * (1 + (sdr_elasticity * df['Price_Pct_Change']))
        df['Predicted_SDR_Journeys'] = df['Predicted_SDR_Journeys'].clip(lower=0)
        
        df['Old_SDR_Revenue'] = df['SDR_Journeys'] * df['Original_SDR']
        df['New_SDR_Revenue'] = df['Predicted_SDR_Journeys'] * df['New_SDR']
        
        df['Revenue_Impact'] = df['New_SDR_Revenue'] - df['Old_SDR_Revenue']
        df['Abs_Revenue_Impact'] = df['Revenue_Impact'].abs()

        # --- 4. DASHBOARD ---
        # =========================================================================
        # --- AUTOMATED: ROUTE ANALYTICS HUB (AUTO-DETECT LINE OF ROUTE) ---
        # =========================================================================
        st.divider()
        st.subheader("Route Analytics Hub")
        st.caption("Type or select an Origin and Destination station. The model will automatically discover the correct line of route, identify intermediate split opportunities, and compare old vs. new price profiles.")
        
        # 1. Compile a sorted, unique list of all stations from across all sequences
        all_stations = sorted(list(set(stn for seq in SEQUENCES.values() for stn in seq)))
        
        # 2. Side-by-side searchable station selectors
        vc1, vc2 = st.columns(2)
        with vc1:
            start_stn = st.selectbox("Select Origin Station:", all_stations, index=0)
        with vc2:
            # Set default destination index to the second item in the list if available
            default_idx = 1 if len(all_stations) > 1 else 0
            end_stn = st.selectbox("Select Destination Station:", all_stations, index=default_idx)
            
        # 3. Background search engine: Discover ALL matching route sequences
        matching_routes = {}  # Store all valid paths found
        
        for seq_name, seq_list in SEQUENCES.items():
            if start_stn in seq_list and end_stn in seq_list:
                s_idx = seq_list.index(start_stn)
                e_idx = seq_list.index(end_stn)
                if s_idx < e_idx:  # Verifies correct travel direction
                    matching_routes[seq_name] = seq_list[s_idx:e_idx + 1]
        
        # 4. Render visualizations based on route selection
        if len(matching_routes) > 0:
            # If multiple routes connect the stations, let the user choose which one to view!
            if len(matching_routes) > 1:
                selected_path_name = st.radio(
                    "🚦 Multiple route corridors found! Select which route path to analyze:",
                    list(matching_routes.keys()),
                    horizontal=True
                )
            else:
                selected_path_name = list(matching_routes.keys())[0]
                
            active_route = matching_routes[selected_path_name]
            st.success(f"**Route Discovered:** Analyzing via the **{selected_path_name}** network corridor.")
            
            # Master pricing maps for both old and new fares
            f_prices_new = df.set_index('Match_ID')['New_SDR'].to_dict()
            f_prices_old = df.set_index('Match_ID')['Original_SDR'].to_dict()
            
            start_clean = start_stn.replace(" ", "")
            end_clean = end_stn.replace(" ", "")
            
            # Direct fare properties for the split-ticket bar baseline
            direct_fare_id = f"{start_clean}-{end_clean}"
            direct_fare_new = f_prices_new.get(direct_fare_id, 0.0)
            
            # --- GATHER DATA FOR SPLIT BAR CHART ---
            chart_data_splits = []
            for i in range(1, len(active_route) - 1):
                mid_stn = active_route[i]
                mid_clean = mid_stn.replace(" ", "")
                
                leg1_id = f"{start_clean}-{mid_clean}"
                leg2_id = f"{mid_clean}-{end_clean}"
                
                leg1_price = f_prices_new.get(leg1_id, 0.0)
                leg2_price = f_prices_new.get(leg2_id, 0.0)
                combined_split_fare = leg1_price + leg2_price
                
                if leg1_price > 0 and leg2_price > 0:
                    chart_data_splits.append({
                        "Intermediate Station": mid_stn.title(),
                        "Split Fare (£)": combined_split_fare,
                        "Leg 1 Price": leg1_price,
                        "Leg 2 Price": leg2_price
                    })

            # --- GATHER DATA FOR OLD VS NEW LINE COMPARATOR ---
            chart_data_comparison = []
            for stn in active_route[1:]:  # Track fares stepping away from the origin
                stn_clean = stn.replace(" ", "")
                flow_id = f"{start_clean}-{stn_clean}"
                
                old_f = f_prices_old.get(flow_id, 0.0)
                new_f = f_prices_new.get(flow_id, 0.0)
                
                if old_f > 0 or new_f > 0:
                    chart_data_comparison.append({
                        "Station": stn.title(),
                        "Old Fare (£)": old_f,
                        "New Fare (£)": new_f,
                        "Change (£)": new_f - old_f
                    })

            # --- RENDER VISUALIZATIONS SIDE-BY-SIDE ---
            import plotly.graph_objects as go
            gc1, gc2 = st.columns(2)
            
            # Left Column: Split Opportunity Bars
            with gc1:
                if chart_data_splits and direct_fare_new > 0:
                    df_splits = pd.DataFrame(chart_data_splits)
                    fig_splits = go.Figure()
                    
                    fig_splits.add_trace(go.Bar(
                        x=df_splits["Intermediate Station"],
                        y=df_splits["Split Fare (£)"],
                        name="Combined Split Price",
                        marker_color='rgb(55, 83, 109)',
                        customdata=df_splits[["Leg 1 Price", "Leg 2 Price"]],
                        hovertemplate="<b>Split Station: %{x}</b><br>Total Split Cost: £%{y:.2f}<br>Leg 1: £%{customdata[0]:.2f}<br>Leg 2: £%{customdata[1]:.2f}<extra></extra>"
                    ))
                    
                    fig_splits.add_shape(
                        type="line", x0=-0.5, y0=direct_fare_new, x1=len(df_splits) - 0.5, y1=direct_fare_new,
                        line=dict(color="Crimson", width=3, dash="dash"),
                    )
                    
                    fig_splits.add_trace(go.Scatter(
                        x=[df_splits["Intermediate Station"].iloc[0]], y=[direct_fare_new],
                        mode="lines", name=f"Direct Fare (£{direct_fare_new:.2f})",
                        line=dict(color="Crimson", width=3, dash="dash"), showlegend=True
                    ))
                    
                    fig_splits.update_layout(
                        title=f"Split Ticket Check: {start_stn.title()} to {end_stn.title()}",
                        xaxis_title="Intermediate Splitting Points", yaxis_title="Total Fare Price (£)",
                        template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_splits, use_container_width=True)
                else:
                    st.info("No internal split points with complete fare combinations found for this specific station pairing.")
            
            # Right Column: Old vs New Price Line Profile (Your Whiteboard Diagram!)
            with gc2:
                if chart_data_comparison:
                    df_comp = pd.DataFrame(chart_data_comparison)
                    fig_comp = go.Figure()
                    
                    # Blue Line for Old Fares
                    fig_comp.add_trace(go.Scatter(
                        x=df_comp["Station"],
                        y=df_comp["Old Fare (£)"],
                        mode="lines+markers",
                        name="Old Fare",
                        line=dict(color="#1f77b4", width=3),
                        marker=dict(size=8),
                        hovertemplate="<b>To: %{x}</b><br>Old Fare: £%{y:.2f}<extra></extra>"
                    ))
                    
                    # Red Line for New Fares
                    fig_comp.add_trace(go.Scatter(
                        x=df_comp["Station"],
                        y=df_comp["New Fare (£)"],
                        mode="lines+markers",
                        name="New Fare",
                        line=dict(color="#d62728", width=3),
                        marker=dict(size=8),
                        customdata=df_comp["Change (£)"],
                        hovertemplate="<b>To: %{x}</b><br>New Fare: £%{y:.2f}<br>Price Change: £%{customdata:+.2f}<extra></extra>"
                    ))
                    
                    fig_comp.update_layout(
                        title=f"Fare Progression Outward from {start_stn.title()}",
                        xaxis_title="Destination Milestone Stops", yaxis_title="Fare Price (£)",
                        template="plotly_white", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        hovermode="x unified"
                    )
                    st.plotly_chart(fig_comp, use_container_width=True)
                else:
                    st.info("No historical comparison data rows found for this selection.")
        else:
            st.info(f"No predefined line of route connects **{start_stn.title()}** to **{end_stn.title()}** in that direction. Please check your origin/destination corridor pairings.")
        # =========================================================================

        st.divider()
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            st.subheader("Top 10 Price Increases")
            st.dataframe(df.sort_values('Opt_Increase', ascending=False).head(10)[['Origin Description', 'Destination Description', 'Base_Price', 'New_SDR', 'Opt_Increase']], 
                         column_config={"Base_Price": st.column_config.NumberColumn("Baseline", format="£%.2f"), "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f"), "Opt_Increase": st.column_config.NumberColumn("Increase", format="£%.2f")}, 
                         use_container_width=True, hide_index=True)
        with r1c2:
            st.subheader("Top 10 Price Decreases")
            dec_disp = df.sort_values('Diff', ascending=True).head(10).copy()
            dec_disp['Diff'] = dec_disp['Diff'].abs()
            st.dataframe(dec_disp[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Diff']], 
                         column_config={"Original_SDR": st.column_config.NumberColumn("Original", format="£%.2f"), "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f"), "Diff": st.column_config.NumberColumn("Decrease", format="£%.2f")}, 
                         use_container_width=True, hide_index=True)

        st.divider()
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            st.subheader("Remaining Split-Ticketing Opportunities")
            f_prices = df.set_index('Match_ID')['New_SDR'].to_dict()
            n_map = df.set_index('Origin_N')['Origin Description'].to_dict()
            gaps = []
            for A in adj:
                for B in adj[A]:
                    if B not in adj: continue
                    for C in adj[B]:
                        id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                        if id_ac in f_prices:
                            thru, s_sum = f_prices[id_ac], f_prices[id_ab] + f_prices.get(id_bc, 0)
                            if thru > (s_sum + 0.01):
                                origin_label = str(n_map.get(A, A)).title()
                                dest_label = str(n_map.get(C, C)).title()
                                split_label = str(n_map.get(B, B)).title()
                                
                                gaps.append({
                                    "Journey": f"{origin_label} to {dest_label}", 
                                    "Split At": split_label, 
                                    "New Fare": thru, 
                                    "Split Fare": s_sum, 
                                    "Difference": round(thru - s_sum, 2)
                                })
            if gaps:
                st.dataframe(pd.DataFrame(gaps).sort_values('Difference', ascending=False).head(300), 
                             column_config={"New Fare": st.column_config.NumberColumn(format="£%.2f"), "Split Fare": st.column_config.NumberColumn(format="£%.2f"), "Difference": st.column_config.NumberColumn(format="£%.2f")},
                             use_container_width=True, hide_index=True)
            else:
                st.success("No Split-Ticket Opportunities Found")
                
            base_prices = df.set_index('Match_ID')['Base_Price'].to_dict()
            split_before = 0
            for A in adj:
                for B in adj[A]:
                    if B not in adj: continue
                    for C in adj[B]:
                        id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                        if id_ac in base_prices:
                            thru = base_prices[id_ac]
                            s_sum = base_prices[id_ab] + base_prices.get(id_bc, 0)
                            if thru > s_sum + 0.01:
                                    split_before += 1

            split_after = len(gaps)
            split_solved = split_before - split_after
            st.markdown(f"**Split-ticket opportunities solved:** {split_solved}<br>**Remaining:** {split_after}", unsafe_allow_html=True)
            
        with r2c2:
            st.subheader("Remaining Long-Buying Opportunities")
            lb_gaps = []
            for path in SEQUENCES.values():
                clean_path = [p.replace(" ", "") for p in path]
                for i, s in enumerate(clean_path):
                    for j, n in enumerate(clean_path[i+1:], i+1):
                        id_sn = f"{s}-{n}"
                        for k, f in enumerate(clean_path[j+1:], j+1):
                            id_sf = f"{s}-{f}"
                            if id_sn in f_prices and id_sf in f_prices:
                                near = f_prices[id_sn]
                                far = f_prices[id_sf]
                                if near > far + 0.01:
                                    lb_gaps.append({
                                        "Origin(A)": path[i].title(),
                                        "Destination(B)": path[j].title(),
                                        "Following Stn(C)": path[k].title(),
                                        "Price to B": near,
                                        "Price to C": far,
                                        "Difference": round(near - far, 2)
                                    })
            if lb_gaps:
               st.dataframe(pd.DataFrame(lb_gaps).sort_values("Difference", ascending=False).head(30),
                   column_config={"Price to B": st.column_config.NumberColumn(format="£%.2f"), "Price to C": st.column_config.NumberColumn(format="£%.2f"), "Difference": st.column_config.NumberColumn(format="£%.2f")},
                   use_container_width=True, hide_index=True)
            else:
                st.info("No Long-Buying Opportunities Found")
                
            lb_before = 0
            for path in SEQUENCES.values():
                clean = [p.replace(" ", "") for p in path]
                for i, s in enumerate(clean):
                    for j, n in enumerate(clean[i+1:], i+1):
                        id_sn = f"{s}-{n}"
                        for k, f in enumerate(clean[j+1:], j+1):
                            id_sf = f"{s}-{f}"
                            if id_sn in base_prices and id_sf in base_prices:
                                if base_prices[id_sn] > base_prices[id_sf] + 0.01:
                                        lb_before += 1
            lb_after = len(lb_gaps)
            lb_solved = lb_before - lb_after
            st.markdown(f"**Long-buying opportunities solved:** {lb_solved}<br>**Remaining:** {lb_after}", unsafe_allow_html=True)

        # --- ROW 3: JOURNEY & REVENUE IMPACT TABLES ---
        st.divider()
        r3c1, r3c2 = st.columns(2)
        with r3c1:
            st.subheader("Biggest Journey Changes")
            st.caption("Flows with price changes affecting the highest volume of SDR journeys")
            journey_changes = df[df['Diff'].abs() > 0.01].sort_values('SDR_Journeys', ascending=False).head(10)
            st.dataframe(journey_changes[['Origin Description', 'Destination Description', 'SDR_Journeys', 'Original_SDR', 'New_SDR', 'Diff']], 
                         column_config={
                             "SDR_Journeys": st.column_config.NumberColumn("Journeys Affected", format="%,d"), 
                             "Original_SDR": st.column_config.NumberColumn("Original Fare", format="£%.2f"), 
                             "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f"), 
                             "Diff": st.column_config.NumberColumn("Price Change", format="£%.2f")
                         },
                         use_container_width=True, hide_index=True)
            
            st.write("") 
            m1, m2 = st.columns(2)
            total_prev_journeys = df['SDR_Journeys'].sum()
            total_new_journeys = df['Predicted_SDR_Journeys'].sum()
            journey_delta = total_new_journeys - total_prev_journeys
            
            m1.metric(label="Previous Total Journeys", value=f"{total_prev_journeys:,.0f}")
            m2.metric(label="New Total Journeys", value=f"{total_new_journeys:,.0f}", delta=f"{journey_delta:+,.0f}")
                         
        with r3c2:
            st.subheader("Biggest Revenue Changes")
            st.caption("Flows with the largest overall financial impact (SDR Volume × Price Change)")
            revenue_changes = df.sort_values('Abs_Revenue_Impact', ascending=False).head(10)
            st.dataframe(revenue_changes[['Origin Description', 'Destination Description', 'SDR_Journeys', 'Diff', 'Revenue_Impact']], 
                         column_config={
                             "SDR_Journeys": st.column_config.NumberColumn("SDR Volume", format="%,d"), 
                             "Diff": st.column_config.NumberColumn("Price Change", format="£%.2f"), 
                             "Revenue_Impact": st.column_config.NumberColumn("Revenue Impact", format="£%,d")
                         },
                         use_container_width=True, hide_index=True)
            
            st.write("") 
            m3, m4 = st.columns(2)
            total_prev_rev = df['Old_SDR_Revenue'].sum()
            total_new_rev = df['New_SDR_Revenue'].sum()
            revenue_delta = total_new_rev - total_prev_rev
            
            m3.metric(label="Previous Total Revenue", value=f"£{total_prev_rev:,.0f}")
            m4.metric(label="New Total Revenue", value=f"£{total_new_rev:,.0f}", delta=f"£{revenue_delta:+,.0f}")

        st.divider()
        st.subheader("Full Fare Summary")
        st.dataframe(df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Status']], 
                     column_config={"Original_SDR": st.column_config.NumberColumn("Original", format="£%.2f"), "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f")},
                     use_container_width=True, hide_index=True)
            
        st.download_button("Download New Fares", convert_df_to_csv(df), "Final_Quartz_Fares.csv", "text/csv")
else:
    st.info("Please upload fare spreadsheets in the sidebar to populate the dynamic optimization model dashboard.")
