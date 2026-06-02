import streamlit as st
import pandas as pd
import math
import os
from collections import defaultdict
import plotly.graph_objects as go

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
    st.caption("Prototype adjuster for Oval fares (part 2) - Optimized High-Speed Engine")

# --- 1. SEQUENCES ---
SEQUENCES = {
    "Wanborough Main Line": ["ASH", "WANBOROUGH", "GUILDFORD", "WORPLESDON", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Alton Main Line": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Chertsey Branch Line": ["CHERTSEY", "ADDLESTONE", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Cobham Branch Line": ["GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLAYGATE", "HINCHLEY WOOD", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"]
}

# --- HELPER FUNCTIONS ---
def round_up(amount, increment):
    if increment <= 0:
        return amount
    return math.ceil(amount / increment) * increment

def derive_fare(base_sdr, fare_type, current_7ds=0.0):
    if fare_type == "SDR":
        return base_sdr
    elif fare_type == "SDS":
        return round_up((base_sdr / 2) * 1.05, 0.10)
    elif fare_type == "CDS":
        return round_up((base_sdr / 2) * 0.85, 0.10)
    elif fare_type == "CDR":
        return round_up(base_sdr * 0.80, 0.10)
    elif fare_type == "7DS":
        return current_7ds
    return base_sdr

# --- 2. SIDEBAR CONTROLS ---
with st.sidebar:
    st.header("Global Configuration Panel")
    
    ticket_options = ["SDR", "SDS", "CDS", "CDR", "7DS"]
    chosen_ticket = st.selectbox("Target Product Architecture:", ticket_options, index=0)
    
    st.markdown("---")
    st.subheader("Boundary Constraints")
    inc_cap = st.slider("Maximum Increase Allowed (%):", 0.0, 1.0, 0.05, step=0.01)
    dec_cap = st.slider("Maximum Decrease Allowed (%):", 0.0, 1.0, 0.15, step=0.01)
    
    st.markdown("---")
    st.subheader("Rounding Rule Matrix")
    sdr_rounding = st.selectbox("SDR Incremental Coin Value (£):", [0.10, 0.50, 1.00, 0.05, 0.00], index=0)
    
    st.markdown("---")
    st.subheader("Risk Guardrails")
    slp_enabled = st.checkbox("Enforce Single-Leg Pricing Symmetry", value=True)
    
    enable_low_vol = st.checkbox("Protect Low-Volume Exceptions", value=True)
    low_vol_threshold = st.number_input("Low Volume Threshold (Journeys):", min_value=1, max_value=1000, value=25, step=5)
    low_vol_action = st.selectbox("Action on Low Volume:", ["Ignore the Cap Completely", "Double the Standard Cap"], index=0)
    
    enable_high_rev = st.checkbox("Protect High-Revenue Risks", value=True)
    high_rev_threshold = st.number_input("High Revenue Milestone Target (£):", min_value=100, max_value=100000, value=2500, step=500)
    high_rev_action = st.selectbox("Action on High Revenue Threshold:", ["Do Not Decrease At All", "Halve the Maximum Allowed Decrease"], index=0)
    
    st.markdown("---")
    st.subheader("Manual Exclusions Registry")
    excluded_splits = st.multiselect("Bypass Split-Ticket Optimizations for:", [])
    excluded_longbuys = st.multiselect("Bypass Long-Buying Mitigations for:", [])
    
    st.markdown("---")
    # CRITICAL SPEED STEP: Elasticity slider does not trigger heavy calculation anymore
    ticket_elasticity = st.slider("Product Demand Elasticity Factor:", -2.5, 0.0, -0.76, step=0.05)
    
    st.markdown("---")
    # Action button so processing engine only compiles when you want it to
    trigger_process = st.button("⚡ Run / Update Optimization Loop", type="primary", use_container_width=True)

st.subheader("Data Intake Source")
uploaded_files = st.file_uploader("Upload Network Source Spreadsheets (Multi-File Selection Supported):", type=["xlsx"], accept_multiple_files=True)

# --- 3. CORE PROCESSING ENGINE (ISOLATED IN SESSION STATE) ---
if uploaded_files:
    # Build unique parameters key to track changes in processing parameters
    current_run_key = (
        len(uploaded_files), chosen_ticket, inc_cap, dec_cap, sdr_rounding,
        slp_enabled, enable_low_vol, low_vol_threshold, low_vol_action,
        enable_high_rev, high_rev_threshold, high_rev_action,
        str(excluded_splits), str(excluded_longbuys)
    )
    
    # Check if we need to regenerate optimized base dataframe
    if "processed_df" not in st.session_state or st.session_state.get("run_key") != current_run_key or trigger_process:
        with st.spinner("Processing optimization matrices (skipping this step on slider changes)..."):
            all_dfs = []
            all_jr_dfs = []
            
            for f in uploaded_files:
                df_main = pd.read_excel(f, sheet_name='Main Sheet', header=1)
                all_dfs.append(df_main)
                try:
                    df_jr_raw = pd.read_excel(f, sheet_name='Journeys and Revenue')
                    all_jr_dfs.append(df_jr_raw)
                except Exception as e:
                    st.error(f"Could not find 'Journeys and Revenue' sheet in {f.name}.")

            df = pd.concat(all_dfs, ignore_index=True)
            df.columns = [str(c).strip() for c in df.columns]
            
            df['Origin Description'] = df.iloc[:, 1].astype(str).str.strip().str.title()
            df['Destination Description'] = df.iloc[:, 3].astype(str).str.strip().str.title()
            
            df['Origin_N'] = df['Origin Description'].str.upper().str.replace(" ", "")
            df['Dest_N'] = df['Destination Description'].str.upper().str.replace(" ", "")
            df['Match_ID'] = df['Origin_N'] + "-" + df['Dest_N']
            
            df['Original_SDR'] = pd.to_numeric(df.iloc[:, 9], errors='coerce').fillna(0.0)
            df['Original_7DS'] = pd.to_numeric(df['7DS'], errors='coerce').fillna(0.0) if '7DS' in df.columns else pd.to_numeric(df.iloc[:, 13], errors='coerce').fillna(0.0)
            
            df['Original_7DS'] = df['Original_7DS'].fillna(df['Original_SDR'] * 3.5)
            df.loc[df['Original_7DS'] <= 0, 'Original_7DS'] = df['Original_SDR'] * 3.5
            
            df = df.sort_values('Original_SDR', ascending=False).drop_duplicates(subset=['Match_ID']).copy()
            
            raw_price_map = df.set_index('Match_ID')['Original_SDR'].to_dict()
            raw_7ds_map = df.set_index('Match_ID')['Original_7DS'].to_dict()

            if all_jr_dfs:
                df_jr = pd.concat(all_jr_dfs, ignore_index=True)
                df_jr.columns = [str(c).strip() for c in df_jr.columns]
                
                df_jr['Origin_N'] = df_jr['True Origin Description'].astype(str).str.upper().str.replace(" ", "")
                df_jr['Dest_N'] = df_jr['True Destination Description'].astype(str).str.upper().str.replace(" ", "")
                df_jr['Match_ID'] = df_jr['Origin_N'] + "-" + df_jr['Dest_N']
                
                product_mapping = {
                    '2BAF': 'SDR', '1BAF': 'SDR', '2AAA': 'SDS', '1AAA': 'SDS',
                    '2ADA': 'CDS', 'ADA': 'CDS', '2BDY': 'CDR', '2MQA': '7DS',
                    '1MQA': '7DS', '2BHA': 'CDR', '2HYV': 'CDR', '2ADO': 'CDS', '2HYU': 'CDS'
                }
                
                df_jr['Product_Clean'] = df_jr['Product Code'].astype(str).str.strip().str.upper()
                df_jr['Standard_Product'] = df_jr['Product_Clean'].map(product_mapping)
                
                df_jr['JOURNEYS'] = pd.to_numeric(df_jr['JOURNEYS'], errors='coerce').fillna(0)
                df_jr['REVENUE'] = pd.to_numeric(df_jr['REVENUE'], errors='coerce').fillna(0.0)
                
                total_jr_summary = df_jr.groupby('Match_ID')['JOURNEYS'].sum().reset_index()
                total_jr_summary.columns = ['Match_ID', 'Total_Journeys']
                
                df_filtered_jr = df_jr[df_jr['Standard_Product'] == chosen_ticket]
                filtered_jr_summary = df_filtered_jr.groupby('Match_ID').agg({'JOURNEYS': 'sum', 'REVENUE': 'sum'}).reset_index()
                filtered_jr_summary.columns = ['Match_ID', 'Filtered_Journeys', 'Filtered_Revenue']
                
                df = df.merge(total_jr_summary, on='Match_ID', how='left')
                df = df.merge(filtered_jr_summary, on='Match_ID', how='left')
                
                df['Total_Journeys'] = df['Total_Journeys'].fillna(0)
                df['Filtered_Journeys'] = df['Filtered_Journeys'].fillna(0)
                df['Filtered_Revenue'] = df['Filtered_Revenue'].fillna(0.0)
            else:
                df['Total_Journeys'] = 0
                df['Filtered_Journeys'] = 0
                df['Filtered_Revenue'] = 0.0
            
            # --- PREPARE BASE GRIDS ---
            def initial_prep(row):
                parts = row['Match_ID'].split("-")
                rev_id = f"{parts[1]}-{parts[0]}"
                highest = max(row['Original_SDR'], raw_price_map.get(rev_id, 0))
                val = highest if slp_enabled else row['Original_SDR']
                return round_up(val, sdr_rounding)

            df['New_SDR'] = df.apply(initial_prep, axis=1)
            df['Base_Price'] = df['New_SDR'].copy()

            def initial_prep_7ds(row):
                parts = row['Match_ID'].split("-")
                rev_id = f"{parts[1]}-{parts[0]}"
                highest = max(row['Original_7DS'], raw_7ds_map.get(rev_id, 0))
                val = highest if slp_enabled else row['Original_7DS']
                return float(val)

            df['New_7DS'] = df.apply(initial_prep_7ds, axis=1)
            df['Base_Price_7DS'] = df['New_7DS'].copy()

            # --- CAPS LOGIC ---
            def calculate_ceiling(row):
                if enable_low_vol and (row['Total_Journeys'] < low_vol_threshold):
                    effective_cap = inc_cap * (999.0 if low_vol_action == "Ignore the Cap Completely" else 2)
                else: effective_cap = inc_cap
                return round_up(row['Original_SDR'] * (1 + effective_cap), sdr_rounding)

            df['Ceiling_Price'] = df.apply(calculate_ceiling, axis=1)

            def calculate_floor(row):
                if enable_high_rev and (row['Filtered_Revenue'] > high_rev_threshold):
                    if high_rev_action == "Do Not Decrease At All": return row['Original_SDR']
                    else: effective_dec_cap = dec_cap / 2
                else: effective_dec_cap = dec_cap
                return round_up(row['Original_SDR'] * (1 - effective_dec_cap), sdr_rounding)

            df['Floor_Price'] = df.apply(calculate_floor, axis=1)

            def calculate_ceiling_7ds(row):
                if enable_low_vol and (row['Total_Journeys'] < low_vol_threshold):
                    effective_cap = inc_cap * (9999.0 if low_vol_action == "Ignore the Cap Completely" else 2)
                else: effective_cap = inc_cap
                return float(row['Original_7DS'] * (1 + effective_cap))

            df['Ceiling_Price_7DS'] = df.apply(calculate_ceiling_7ds, axis=1)

            def calculate_floor_7ds(row):
                if enable_high_rev and (row['Filtered_Revenue'] > high_rev_threshold):
                    if high_rev_action == "Do Not Decrease At All": return row['Original_7DS']
                    else: effective_dec_cap = dec_cap / 2
                else: effective_dec_cap = dec_cap
                return float(row['Original_7DS'] * (1 - effective_dec_cap))

            df['Floor_Price_7DS'] = df.apply(calculate_floor_7ds, axis=1)

            # --- OPTIMIZATION SWEEPS ---
            adj = defaultdict(list)
            for mid in raw_price_map.keys():
                o, d = mid.split("-")
                adj[o].append(d)

            curr_sdr = df.set_index('Match_ID')['New_SDR'].to_dict()
            curr_7ds = df.set_index('Match_ID')['New_7DS'].to_dict()

            for _ in range(2):
                for A in adj:
                    for B in adj[A]:
                        if B not in adj: continue
                        for C in adj[B]:
                            id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                            
                            if id_ac in curr_sdr:
                                thru, s_sum = curr_sdr[id_ac], curr_sdr[id_ab] + curr_sdr.get(id_bc, 9999)
                                if s_sum < (thru - 0.009):
                                    if id_bc in curr_sdr and id_bc not in excluded_splits:
                                        curr_sdr[id_bc] = min(round_up(curr_sdr[id_bc] + (thru - s_sum)/2, sdr_rounding), df.loc[df['Match_ID']==id_bc, 'Ceiling_Price'].values[0])
                                    if id_ac not in excluded_splits:
                                        curr_sdr[id_ac] = max(round_up(curr_sdr[id_ab] + curr_sdr[id_bc], sdr_rounding), df.loc[df['Match_ID']==id_ac, 'Floor_Price'].values[0])

                            if id_ac in curr_7ds:
                                thru, s_sum = curr_7ds[id_ac], curr_7ds[id_ab] + curr_7ds.get(id_bc, 9999)
                                if s_sum < (thru - 0.009):
                                    if id_bc in curr_7ds and id_bc not in excluded_splits:
                                        curr_7ds[id_bc] = min(curr_7ds[id_bc] + (thru - s_sum)/2, df.loc[df['Match_ID']==id_bc, 'Ceiling_Price_7DS'].values[0])
                                    if id_ac not in excluded_splits:
                                        curr_7ds[id_ac] = max(curr_7ds[id_ab] + curr_7ds[id_bc], df.loc[df['Match_ID']==id_ac, 'Floor_Price_7DS'].values[0])

                for path in SEQUENCES.values():
                    for i, s in enumerate(path):
                        s_c = s.replace(" ","")
                        for j, n in enumerate(path[i+1:], i+1):
                            n_c = n.replace(" ","")
                            for k, f in enumerate(path[j+1:], j+1):
                                f_c = f.replace(" ","")
                                id_near, id_far = f"{s_c}-{n_c}", f"{s_c}-{f_c}"
                                
                                if id_near in curr_sdr and id_far in curr_sdr:
                                    if curr_sdr[id_near] > curr_sdr[id_far] and id_near not in excluded_longbuys:
                                        curr_sdr[id_near] = max(curr_sdr[id_far], df.loc[df['Match_ID']==id_near, 'Floor_Price'].values[0])
                                if id_near in curr_7ds and id_far in curr_7ds:
                                    if curr_7ds[id_near] > curr_7ds[id_far] and id_near not in excluded_longbuys:
                                        curr_7ds[id_near] = max(curr_7ds[id_far], df.loc[df['Match_ID']==id_near, 'Floor_Price_7DS'].values[0])

            df['New_SDR'] = df['Match_ID'].map(curr_sdr)
            df['New_7DS'] = df['Match_ID'].map(curr_7ds)

            if slp_enabled:
                # SDR SLP
                final_prices_sdr = df.set_index('Match_ID')['New_SDR'].to_dict()
                for mid in list(final_prices_sdr.keys()):
                    o, d = mid.split("-")
                    rev = f"{d}-{o}"
                    if rev in final_prices_sdr:
                        unified = max(final_prices_sdr[mid], final_prices_sdr[rev])
                        c1, f1 = df.loc[df['Match_ID']==mid, ['Ceiling_Price','Floor_Price']].values[0]
                        c2, f2 = df.loc[df['Match_ID']==rev, ['Ceiling_Price','Floor_Price']].values[0]
                        final_prices_sdr[mid] = final_prices_sdr[rev] = round_up(min(max(unified, min(f1, f2)), max(c1, c2)), sdr_rounding)
                df['New_SDR'] = df['Match_ID'].map(final_prices_sdr)

                # 7DS SLP
                final_prices_7ds = df.set_index('Match_ID')['New_7DS'].to_dict()
                for mid in list(final_prices_7ds.keys()):
                    o, d = mid.split("-")
                    rev = f"{d}-{o}"
                    if rev in final_prices_7ds:
                        unified = max(final_prices_7ds[mid], final_prices_7ds[rev])
                        c1, f1 = df.loc[df['Match_ID']==mid, ['Ceiling_Price_7DS','Floor_Price_7DS']].values[0]
                        c2, f2 = df.loc[df['Match_ID']==rev, ['Ceiling_Price_7DS','Floor_Price_7DS']].values[0]
                        final_prices_7ds[mid] = final_prices_7ds[rev] = float(min(max(unified, min(f1, f2)), max(c1, c2)))
                df['New_7DS'] = df['Match_ID'].map(final_prices_7ds)

            # Store computed static matrix inside Streamlit memory state
            st.session_state["processed_df"] = df
            st.session_state["run_key"] = current_run_key

    # Fetch the cached baseline dataframe instantly
    df = st.session_state["processed_df"].copy()

    # --- 4. FAST DYNAMIC RECALCULATIONS LINKED TO WIDGETS ---
    # These calculations execute instantly when updating elasticity sliders or selectors
    df['Display_Original_Fare'] = df.apply(lambda r: derive_fare(r['Original_SDR'], chosen_ticket, r['Original_7DS']), axis=1)
    df['Display_New_Fare'] = df.apply(lambda r: derive_fare(r['New_SDR'], chosen_ticket, r['New_7DS']), axis=1)

    df['Diff'] = df['Display_New_Fare'] - df['Display_Original_Fare']
    df['Opt_Increase'] = df['Display_New_Fare'] - df.apply(lambda r: derive_fare(r['Base_Price'], chosen_ticket, r['Base_Price_7DS']), axis=1)
    df['Status'] = df['Diff'].apply(lambda x: "Increased" if x > 0.01 else ("Decreased" if x < -0.01 else "Unchanged"))
    
    safe_orig_fare = df['Display_Original_Fare'].replace(0, 1)
    df['Price_Pct_Change'] = df['Diff'] / safe_orig_fare
    
    df['Predicted_Journeys'] = df['Filtered_Journeys'] * (1 + (ticket_elasticity * df['Price_Pct_Change']))
    df['Predicted_Journeys'] = df['Predicted_Journeys'].clip(lower=0)
    
    df['Old_Ticket_Revenue'] = df['Filtered_Journeys'] * df['Display_Original_Fare']
    df['New_Ticket_Revenue'] = df['Predicted_Journeys'] * df['Display_New_Fare']
    
    df['Revenue_Impact'] = df['New_Ticket_Revenue'] - df['Old_Ticket_Revenue']
    df['Abs_Revenue_Impact'] = df['Revenue_Impact'].abs()

    # --- 5. RENDER USER DASHBOARD AND GRAPHS ---
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.metric("Total Flows Identified", len(df))
    with sc2:
        increased_flows = len(df[df['Status'] == "Increased"])
        st.metric("Flows Optimized Upward", f"{increased_flows} flows")
    with sc3:
        net_impact = df['Revenue_Impact'].sum()
        st.metric("Total Network Net Yield Impact", f"£{net_impact:+,.2f}")

    tab1, tab2 = st.tabs(["📊 Network Yield Impact Hub", "📋 Detailed Evaluation Data Log"])
    
    with tab1:
        m1, m2 = st.columns(2)
        with m1:
            st.write("**Top Revenue Deficit Flows (Risk Drivers)**")
            df_loss = df[df['Status']=='Decreased'].sort_values('Abs_Revenue_Impact', ascending=False).head(10)
            st.dataframe(df_loss[['Origin Description', 'Destination Description', 'Filtered_Journeys', 'Diff', 'Revenue_Impact']],
                         column_config={
                             "Filtered_Journeys": st.column_config.NumberColumn("Volume", format="%,d"),
                             "Diff": st.column_config.NumberColumn("Price Change", format="£%.2f"),
                             "Revenue_Impact": st.column_config.NumberColumn("Revenue Impact", format="£%,d")
                         }, use_container_width=True, hide_index=True)
        with m2:
            st.write("**Top Revenue Capture Flows (Opportunity Optimization)**")
            df_gain = df[df['Status']=='Increased'].sort_values('Abs_Revenue_Impact', ascending=False).head(10)
            st.dataframe(df_gain[['Origin Description', 'Destination Description', 'Filtered_Journeys', 'Diff', 'Revenue_Impact']],
                         column_config={
                             "Filtered_Journeys": st.column_config.NumberColumn("Volume", format="%,d"),
                             "Diff": st.column_config.NumberColumn("Price Change", format="£%.2f"),
                             "Revenue_Impact": st.column_config.NumberColumn("Revenue Impact", format="£%,d")
                         }, use_container_width=True, hide_index=True)
            
        st.write("") 
        m3, m4 = st.columns(2)
        total_prev_rev = df['Old_Ticket_Revenue'].sum()
        total_new_rev = df['New_Ticket_Revenue'].sum()
        revenue_delta = total_new_rev - total_prev_rev
        
        m3.metric(label=f"Previous {chosen_ticket} Yield", value=f"£{total_prev_rev:,.0f}")
        m4.metric(label=f"New Predicted {chosen_ticket} Yield", value=f"£{total_new_rev:,.0f}", delta=f"£{revenue_delta:+,.0f}")

    with tab2:
        st.subheader("Full Context Fare Summary")
        output_df = df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Display_Original_Fare', 'Display_New_Fare', 'Status']].copy()
        st.dataframe(output_df, column_config={
            "Original_SDR": st.column_config.NumberColumn("Base Orig SDR", format="£%.2f"), 
            "New_SDR": st.column_config.NumberColumn("Base New SDR", format="£%.2f"),
            "Display_Original_Fare": st.column_config.NumberColumn(f"Orig {chosen_ticket}", format="£%.2f"),
            "Display_New_Fare": st.column_config.NumberColumn(f"New {chosen_ticket}", format="£%.2f")
        }, use_container_width=True, hide_index=True)
            
        st.download_button("Download Full Optimised Fares Dataset", convert_df_to_csv(df), "optimised_fares_grid.csv", "text/csv", use_container_width=True)

    # =========================================================================
    # --- AUTOMATED: ROUTE ANALYTICS HUB (AUTO-DETECT LINE OF ROUTE) ---
    # =========================================================================
    st.divider()
    st.subheader("Route Analytics Hub")
    st.caption(f"Analyzing network corridors using **{chosen_ticket}** pricing structures. The engine automatically handles directionality and filters structural duplicates.")
    
    all_stations = sorted(list(set(stn for seq in SEQUENCES.values() for stn in seq)))
    
    vc1, vc2 = st.columns(2)
    with vc1:
        start_stn = st.selectbox("Select Origin Station:", all_stations, index=0)
    with vc2:
        default_idx = 1 if len(all_stations) > 1 else 0
        end_stn = st.selectbox("Select Destination Station:", all_stations, index=default_idx)
                 
    matching_routes = {}
    for seq_name, seq_list in SEQUENCES.items():
        if start_stn in seq_list and end_stn in seq_list:
            s_idx = seq_list.index(start_stn)
            e_idx = seq_list.index(end_stn)
            
            if s_idx < e_idx:
                path_slice = tuple(seq_list[s_idx:e_idx + 1])
                direction_label = ""
            else:
                path_slice = tuple(seq_list[e_idx:s_idx + 1][::-1])
                direction_label = " (Reverse)"
                
            if path_slice not in matching_routes:
                matching_routes[path_slice] = []
            matching_routes[path_slice].append(f"{seq_name}{direction_label}")
    
    if len(matching_routes) > 0:
        if len(matching_routes) > 1:
            display_options = {}
            for path_slice, seq_names in matching_routes.items():
                primary_name = seq_names[0]
                display_options[primary_name] = list(path_slice)
            
            selected_path_name = st.radio(
                " Multiple distinct route corridors found! Select which route path to analyze:",
                list(display_options.keys()), horizontal=True
            )
            active_route = display_options[selected_path_name]
            st.success(f"**Route Discovered:** Analyzing via the **{selected_path_name}** corridor.")
        else:
            active_route = list(matching_routes.keys())[0]
            associated_sequences = matching_routes[active_route]
            st.success(f"**Route Discovered:** Analyzing via the **{associated_sequences[0]}** corridor.")
        
        sdr_prices = df.set_index('Match_ID')['New_SDR'].to_dict()
        seasons_prices = df.set_index('Match_ID')['New_7DS'].to_dict()
        f_prices_new = df.set_index('Match_ID')['Display_New_Fare'].to_dict()
        f_prices_old = df.set_index('Match_ID')['Display_Original_Fare'].to_dict()
        
        if chosen_ticket in ["SDR", "CDR"]:
            alt_product = "CDR"
        elif chosen_ticket in ["SDS", "CDS"]:
            alt_product = "CDS"
        else:
            alt_product = chosen_ticket
    
        start_clean = start_stn.replace(" ", "")
        end_clean = end_stn.replace(" ", "")
        
        direct_fare_id = f"{start_clean}-{end_clean}"
        direct_fare_new = f_prices_new.get(direct_fare_id, 0.0)
        
        chart_data_splits = []
        for i in range(1, len(active_route) - 1):
            mid_stn = active_route[i]
            mid_clean = mid_stn.replace(" ", "")
            
            leg1_id = f"{start_clean}-{mid_clean}"
            leg2_id = f"{mid_clean}-{end_clean}"
            
            if chosen_ticket == "7DS":
                l1_p = seasons_prices.get(leg1_id, 0.0)
                l2_p = seasons_prices.get(leg2_id, 0.0)
                if l1_p > 0 and l2_p > 0:
                    chart_data_splits.append({
                        "Intermediate Station": mid_stn.title(),
                        "Pure Split": l1_p + l2_p,
                        "Pure L1": l1_p, "Pure L2": l2_p,
                        "Mix A": 0.0, "Mix A L1": 0.0, "Mix A L2": 0.0,
                        "Mix B": 0.0, "Mix B L1": 0.0, "Mix B L2": 0.0
                    })
            else:
                base_sdr_l1 = sdr_prices.get(leg1_id, 0.0)
                base_sdr_l2 = sdr_prices.get(leg2_id, 0.0)
                
                if base_sdr_l1 > 0 and base_sdr_l2 > 0:
                    l1_primary = derive_fare(base_sdr_l1, chosen_ticket)
                    l2_primary = derive_fare(base_sdr_l2, chosen_ticket)
                    l1_alt = derive_fare(base_sdr_l1, alt_product)
                    l2_alt = derive_fare(base_sdr_l2, alt_product)
                    
                    chart_data_splits.append({
                        "Intermediate Station": mid_stn.title(),
                        "Pure Split": l1_primary + l2_primary,
                        "Pure L1": l1_primary, "Pure L2": l2_primary,
                        "Mix A": l1_primary + l2_alt,
                        "Mix A L1": l1_primary, "Mix A L2": l2_alt,
                        "Mix B": l1_alt + l2_primary,
                        "Mix B L1": l1_alt, "Mix B L2": l2_primary
                    })

        chart_data_comparison = []
        for stn in active_route[1:]:
            stn_clean = stn.replace(" ", "")
            flow_id = f"{start_clean}-{stn_clean}"
            old_f = f_prices_old.get(flow_id, 0.0)
            new_f = f_prices_new.get(flow_id, 0.0)
            if old_f > 0 or new_f > 0:
                chart_data_comparison.append({
                    "Station": stn.title(), "Old Fare (£)": old_f, "New Fare (£)": new_f, "Change (£)": new_f - old_f
                })

        gc1, gc2 = st.columns(2)
        with gc1:
            if chart_data_splits and direct_fare_new > 0:
                df_splits = pd.DataFrame(chart_data_splits)
                fig_splits = go.Figure()
                
                fig_splits.add_trace(go.Bar(
                    x=df_splits["Intermediate Station"], y=df_splits["Pure Split"],
                    name=f"Pure Split ({chosen_ticket})", marker_color='rgb(55, 83, 109)',
                    customdata=df_splits[["Pure L1", "Pure L2"]],
                    hovertemplate="<b>Split Station: %{x}</b><br>Total Cost: £%{y:.2f}<br>L1: £%{customdata[0]:.2f}<br>L2: £%{customdata[1]:.2f}<extra></extra>"
                ))
                
                if chosen_ticket != "7DS" and chosen_ticket != alt_product:
                    fig_splits.add_trace(go.Bar(
                        x=df_splits["Intermediate Station"], y=df_splits["Mix A"],
                        name=f"Combo A ({chosen_ticket}+{alt_product})", marker_color='rgb(26, 118, 141)',
                        customdata=df_splits[["Mix A L1", "Mix A L2"]],
                        hovertemplate="<b>Split: %{x}</b><br>Total: £%{y:.2f}<br>L1: £%{customdata[0]:.2f}<br>L2: £%{customdata[1]:.2f}<extra></extra>"
                    ))
                    fig_splits.add_trace(go.Bar(
                        x=df_splits["Intermediate Station"], y=df_splits["Mix B"],
                        name=f"Combo B ({alt_product}+{chosen_ticket})", marker_color='rgb(158, 201, 225)',
                        customdata=df_splits[["Mix B L1", "Mix B L2"]],
                        hovertemplate="<b>Split: %{x}</b><br>Total: £%{y:.2f}<br>L1: £%{customdata[0]:.2f}<br>L2: £%{customdata[1]:.2f}<extra></extra>"
                    ))
                
                fig_splits.add_shape(type="line", x0=-0.5, y0=direct_fare_new, x1=len(df_splits) - 0.5, y1=direct_fare_new, line=dict(color="Crimson", width=3, dash="dash"))
                fig_splits.add_trace(go.Scatter(x=[df_splits["Intermediate Station"].iloc[0]], y=[direct_fare_new], mode="lines", name=f"Direct Fare (£{direct_fare_new:.2f})", line=dict(color="Crimson", width=3, dash="dash")))
                fig_splits.update_layout(title=f"Split Validation Check", xaxis_title="Split Points", yaxis_title="Fare (£)", barmode='group', template="plotly_white")
                st.plotly_chart(fig_splits, use_container_width=True)
            else:
                st.info("No complete matching intermediate split steps identified along this path segment.")
        
        with gc2:
            if chart_data_comparison:
                df_comp = pd.DataFrame(chart_data_comparison)
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Scatter(x=df_comp["Station"], y=df_comp["Old Fare (£)"], mode="lines+markers", name="Old Fare", line=dict(color="#1f77b4", width=3)))
                fig_comp.add_trace(go.Scatter(x=df_comp["Station"], y=df_comp["New Fare (£)"], mode="lines+markers", name="New Fare", line=dict(color="#d62728", width=3), customdata=df_comp["Change (£)"], hovertemplate="<b>To: %{x}</b><br>New: £%{y:.2f}<br>Change: £%{customdata:+.2f}<extra></extra>"))
                fig_comp.update_layout(title=f"Fare Progression Matrix", xaxis_title="Milestone Stop", yaxis_title="Price (£)", template="plotly_white", hovermode="x unified")
                st.plotly_chart(fig_comp, use_container_width=True)
    else:
        st.info("No predefined network routing coordinates match this specific combination direction.")
