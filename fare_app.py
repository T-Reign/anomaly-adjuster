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
    st.caption("Prototype adjuster for Oval fares (part 2)")

# --- 1. SEQUENCES ---
SEQUENCES = {
    "Wanborough Main Line": ["ASH", "WANBOROUGH", "GUILDFORD", "WORPLESDON", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Alton Main Line": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Via Woking": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Via Ascot": ["ZONE R1256 LONDON", "LONDON BR", "QUEENSTOWN ROAD(BATTERSEA)", "CLAPHAM JUNCTION LONDON", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "FARNHAM", "BENTLEY", "ALTON"],
    "Reading-Alton": ["READING", "EARLEY", "WINNERSH TRIANGLE", "WINNERSH", "WOKINGHAM", "BRACKNELL", "MARTINS HERON", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "FARNHAM", "BENTLEY", "ALTON"],
    "Reading-Guilford": ["READING", "EARLEY", "WINNERSH TRIANGLE", "WINNERSH", "WOKINGHAM", "BRACKNELL", "MARTINS HERON", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD"],
    "Bagshot-Ashtead": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "ASHTEAD"],
    "Alton-Ashtead": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "ASHTEAD"],
    "Bagshot-Dorking": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "BOX HILL & WESTHUMBLE", "DORKING"],
    "Alton-Dorking": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "BOX HILL & WESTHUMBLE", "DORKING"],
    "Via Surbiton": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "HINCHLEY WOOD", "CLAYGATE", "OXSHOTT"],
    "Via Walton-On-Thames": ["BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "HINCHLEY WOOD", "CLAYGATE", "OXSHOTT"],
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
    if pd.isna(x) or x <= 0: 
        return 0.0
    if base < 0.01: return round(float(x), 2)
    multiplied = round(float(x), 2) * (1/base)
    rounded_up = math.ceil(round(multiplied, 7)) / (1/base)
    return round(rounded_up, 2)

# --- Dynamic Multi-Fare Calculation Helper Function ---
def derive_fare(base_sdr, fare_type, current_7ds=0.0):
    if pd.isna(base_sdr) or base_sdr <= 0:
        return 0.0
    if fare_type == "SDR":
        return base_sdr
    elif fare_type == "SDS":
        return base_sdr * 0.5
    elif fare_type == "CDS":
        sds_price = base_sdr * 0.5
        return round((sds_price * 0.69) * 10) / 10  # Rounded to nearest 10p
    elif fare_type == "CDR":
        sds_price = base_sdr * 0.5
        cds_price = round((sds_price * 0.69) * 10) / 10
        return cds_price * 2
    elif fare_type == "7DS":
        return current_7ds
    return base_sdr

# --- 2. SIDEBAR ---
st.sidebar.header("1. Ticket Type Config")
ticket_options = {
    "SDR (Standard Day Return)": "SDR",
    "SDS (Standard Day Single)": "SDS",
    "CDS (Cheap Day Single)": "CDS",
    "CDR (Cheap Day Return)": "CDR",
    "7DS (7-Day Season Ticket)": "7DS"
}
selected_ticket_label = st.sidebar.selectbox(" Analysis Mode Ticket Type:", list(ticket_options.keys()))
chosen_ticket = ticket_options[selected_ticket_label]

st.sidebar.header("2. Split-Ticket Exclusions")
raw_split_ex = st.sidebar.text_area("Flows to exclude from split adjustment:", value="Reading-Earley")
excluded_splits = {line.strip().upper().replace(" ", "") for line in raw_split_ex.split('\n') if "-" in line}

st.sidebar.header("3. Long-Buy Exclusions")
raw_lb_ex = st.sidebar.text_area("Flows to exclude from long-buy adjustment:", value="Aldershot-Oxshott")
excluded_longbuys = {line.strip().upper().replace(" ", "") for line in raw_lb_ex.split('\n') if "-" in line}

st.sidebar.header("4. Optimisation Settings")
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
ticket_elasticity = st.sidebar.slider("Demand Elasticity", -2.0, 0.0, -0.6, step=0.05)

uploaded_files = st.sidebar.file_uploader("Upload Fare Spreadsheets", type=["xlsx"], accept_multiple_files=True)

# --- 3. PROCESSING & STORAGE ENGINE ---
if uploaded_files:
    # Check if we need to run the core mathematical optimization model
    # We only run it if it hasn't run yet, or if a configuration setting changes
    if "optimized_df" not in st.session_state:
        with st.spinner("Running Heavy Core Optimization Loops... (This happens once)"):
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
        
        df['Original_SDS'] = pd.to_numeric(df.iloc[:, 7], errors='coerce').fillna(0.0)  # Col H
        df['Original_CDS'] = pd.to_numeric(df.iloc[:, 8], errors='coerce').fillna(0.0)  # Col I
        df['Original_SDR'] = pd.to_numeric(df.iloc[:, 9], errors='coerce').fillna(0.0)  # Col J
        df['Original_CDR'] = pd.to_numeric(df.iloc[:, 10], errors='coerce').fillna(0.0) # Col K
        df['Original_7DS'] = pd.to_numeric(df['7DS'], errors='coerce').fillna(0.0) if '7DS' in df.columns else pd.to_numeric(df.iloc[:, 13], errors='coerce').fillna(0.0)
        # Extracting the new Super Off-Peak columns from your main sheet layout
        df['Original_EVA'] = pd.to_numeric(df.iloc[:, 12], errors='coerce').fillna(0.0) # Col M
        df['Original_SUA'] = pd.to_numeric(df.iloc[:, 13], errors='coerce').fillna(0.0) # Col N
        df['Original_EVB'] = pd.to_numeric(df.iloc[:, 14], errors='coerce').fillna(0.0) # Col O
        df['Original_SUB'] = pd.to_numeric(df.iloc[:, 15], errors='coerce').fillna(0.0) # Col P
        
        # Helper to find any existing baseline Super Off-Peak fare for reference
        def get_old_sop(row, ticket_type):
            if ticket_type in ["CDR", "SDR"]:
                val = row['Original_EVB'] if row['Original_EVB'] > 0 else row['Original_SUB']
            else:
                val = row['Original_EVA'] if row['Original_EVA'] > 0 else row['Original_SUA']
            return float(val)
        
        df['Old_Super_OffPeak'] = df.apply(lambda r: get_old_sop(r, chosen_ticket), axis=1)
        # Guardrail: Catch any blank or 0 values for 7DS and apply standard formula fallback
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
                '2BAF': 'SDR', '1BAF': 'SDR',
                '2AAA': 'SDS', '1AAA': 'SDS',
                '2ADA': 'CDS', 'ADA': 'CDS',
                '2BDY': 'CDR',
                '2MQA': '7DS', '1MQA': '7DS',
                
                # Super Off-Peak shifts to Standard Off-Peak pipelines
                '2BHA': 'CDR', '2HYV': 'CDR',  # EVB & SUB returns migrate to CDR
                '2ADO': 'CDS', '2HYU': 'CDS'   # EVA & SUA singles migrate to CDS
            }
            
            df_jr['Product_Clean'] = df_jr['Product Code'].astype(str).str.strip().str.upper()
            df_jr['Standard_Product'] = df_jr['Product_Clean'].map(product_mapping)
            
            df_jr['JOURNEYS'] = pd.to_numeric(df_jr['JOURNEYS'], errors='coerce').fillna(0)
            df_jr['REVENUE'] = pd.to_numeric(df_jr['REVENUE'], errors='coerce').fillna(0.0)
            
            total_jr_summary = df_jr.groupby('Match_ID')['JOURNEYS'].sum().reset_index()
            total_jr_summary.columns = ['Match_ID', 'Total_Journeys']
            
            df_filtered_jr = df_jr[df_jr['Standard_Product'] == chosen_ticket]
            filtered_jr_summary = df_filtered_jr.groupby('Match_ID').agg({
                'JOURNEYS': 'sum',
                'REVENUE': 'sum'
            }).reset_index()
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
        
        # --- PREPARE SDR GRIDS ---
        def initial_prep(row):
            parts = row['Match_ID'].split("-")
            rev_id = f"{parts[1]}-{parts[0]}"
            highest = max(row['Original_SDR'], raw_price_map.get(rev_id, 0))
            val = highest if slp_enabled else row['Original_SDR']
            return round_up(val, sdr_rounding)

        df['New_SDR'] = df.apply(initial_prep, axis=1)
        df['Base_Price'] = df['New_SDR'].copy()

        # --- PREPARE 7DS GRIDS (PRESERVING PRECISION FLOATS) ---
        def initial_prep_7ds(row):
            parts = row['Match_ID'].split("-")
            rev_id = f"{parts[1]}-{parts[0]}"
            highest = max(row['Original_7DS'], raw_7ds_map.get(rev_id, 0))
            val = highest if slp_enabled else row['Original_7DS']
            return float(val)

        df['New_7DS'] = df.apply(initial_prep_7ds, axis=1)
        df['Base_Price_7DS'] = df['New_7DS'].copy()

        # --- CALCULATE SDR CEILING & FLOOR CAPS ---
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
            if enable_high_rev and (row['Filtered_Revenue'] > high_rev_threshold):
                if high_rev_action == "Do Not Decrease At All":
                    return row['Original_SDR']
                else:
                    effective_dec_cap = dec_cap / 2
            else:
                effective_dec_cap = dec_cap
            raw_floor = row['Original_SDR'] * (1 - effective_dec_cap)
            return round_up(raw_floor, sdr_rounding)

        df['Floor_Price'] = df.apply(calculate_floor, axis=1)

        # --- CALCULATE 7DS CEILING & FLOOR CAPS ---
        def calculate_ceiling_7ds(row):
            if enable_low_vol and (row['Total_Journeys'] < low_vol_threshold):
                if low_vol_action == "Ignore the Cap Completely":
                    return 99999.0
                else:
                    effective_cap = inc_cap * 2
            else:
                effective_cap = inc_cap
            return float(row['Original_7DS'] * (1 + effective_cap))

        df['Ceiling_Price_7DS'] = df.apply(calculate_ceiling_7ds, axis=1)

        def calculate_floor_7ds(row):
            if enable_high_rev and (row['Filtered_Revenue'] > high_rev_threshold):
                if high_rev_action == "Do Not Decrease At All":
                    return row['Original_7DS']
                else:
                    effective_dec_cap = dec_cap / 2
            else:
                effective_dec_cap = dec_cap
            return float(row['Original_7DS'] * (1 - effective_dec_cap))

        df['Floor_Price_7DS'] = df.apply(calculate_floor_7ds, axis=1)

        # --- MAP ADJACENCY MATRIX NETWORK ---
        adj = defaultdict(list)
        for mid in raw_price_map.keys():
            o, d = mid.split("-")
            adj[o].append(d)

        # --- TWIN SEPARATE OPTIMISATION LOOPS ---
        curr_sdr = df.set_index('Match_ID')['New_SDR'].to_dict()
        curr_7ds = df.set_index('Match_ID')['New_7DS'].to_dict()

        for _ in range(2):
            for A in adj:
                for B in adj[A]:
                    if B not in adj: continue
                    for C in adj[B]:
                        id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                        
                        # Fix SDR split ticketing anomalies
                        if id_ac in curr_sdr:
                            thru, s_sum = curr_sdr[id_ac], curr_sdr[id_ab] + curr_sdr.get(id_bc, 9999)
                            if s_sum < (thru - 0.009):
                                if id_bc in curr_sdr and id_bc not in excluded_splits:
                                    pot_inc = round_up(curr_sdr[id_bc] + (thru - s_sum)/2, sdr_rounding)
                                    curr_sdr[id_bc] = min(pot_inc, df.loc[df['Match_ID']==id_bc, 'Ceiling_Price'].values[0])
                                if id_ac not in excluded_splits:
                                    pot_dec = round_up(curr_sdr[id_ab] + curr_sdr[id_bc], sdr_rounding)
                                    curr_sdr[id_ac] = max(pot_dec, df.loc[df['Match_ID']==id_ac, 'Floor_Price'].values[0])

                        # Fix 7DS split ticketing anomalies (Pure Float Math)
                        if id_ac in curr_7ds:
                            thru, s_sum = curr_7ds[id_ac], curr_7ds[id_ab] + curr_7ds.get(id_bc, 9999)
                            if s_sum < (thru - 0.009):
                                if id_bc in curr_7ds and id_bc not in excluded_splits:
                                    pot_inc = curr_7ds[id_bc] + (thru - s_sum)/2
                                    curr_7ds[id_bc] = min(pot_inc, df.loc[df['Match_ID']==id_bc, 'Ceiling_Price_7DS'].values[0])
                                if id_ac not in excluded_splits:
                                    pot_dec = curr_7ds[id_ab] + curr_7ds[id_bc]
                                    curr_7ds[id_ac] = max(pot_dec, df.loc[df['Match_ID']==id_ac, 'Floor_Price_7DS'].values[0])
            
            # Line of route long buying corridor loops
            for path in SEQUENCES.values():
                for i, s in enumerate(path):
                    s_c = s.replace(" ","")
                    for j, n in enumerate(path[i+1:], i+1):
                        n_c = n.replace(" ","")
                        for k, f in enumerate(path[j+1:], j+1):
                            f_c = f.replace(" ","")
                            id_near, id_far = f"{s_c}-{n_c}", f"{s_c}-{f_c}"
                            
                            # Check long buying for SDR
                            if id_near in curr_sdr and id_far in curr_sdr:
                                if curr_sdr[id_near] > curr_sdr[id_far] and id_near not in excluded_longbuys:
                                    curr_sdr[id_near] = max(curr_sdr[id_far], df.loc[df['Match_ID']==id_near, 'Floor_Price'].values[0])
                                    
                            # Check long buying for 7DS
                            if id_near in curr_7ds and id_far in curr_7ds:
                                if curr_7ds[id_near] > curr_7ds[id_far] and id_near not in excluded_longbuys:
                                    curr_7ds[id_near] = max(curr_7ds[id_far], df.loc[df['Match_ID']==id_near, 'Floor_Price_7DS'].values[0])

        df['New_SDR'] = df['Match_ID'].map(curr_sdr)
        df['New_7DS'] = df['Match_ID'].map(curr_7ds)

        # --- SINGLE-LEG DIRECTIONAL PRICING SYNCHRONISATION ---
        if slp_enabled:
            # Process SDR directional alignment
            final_prices_sdr = df.set_index('Match_ID')['New_SDR'].to_dict()
            for mid in list(final_prices_sdr.keys()):
                o, d = mid.split("-")
                rev = f"{d}-{o}"
                if rev in final_prices_sdr:
                    unified = max(final_prices_sdr[mid], final_prices_sdr[rev])
                    c1, f1 = df.loc[df['Match_ID']==mid, ['Ceiling_Price','Floor_Price']].values[0]
                    c2, f2 = df.loc[df['Match_ID']==rev, ['Ceiling_Price','Floor_Price']].values[0]
                    final_val = min(max(unified, min(f1, f2)), max(c1, c2))
                    final_prices_sdr[mid] = final_prices_sdr[rev] = round_up(final_val, sdr_rounding)
            df['New_SDR'] = df['Match_ID'].map(final_prices_sdr)

            # Process 7DS directional alignment
            final_prices_7ds = df.set_index('Match_ID')['New_7DS'].to_dict()
            for mid in list(final_prices_7ds.keys()):
                o, d = mid.split("-")
                rev = f"{d}-{o}"
                if rev in final_prices_7ds:
                    unified = max(final_prices_7ds[mid], final_prices_7ds[rev])
                    c1, f1 = df.loc[df['Match_ID']==mid, ['Ceiling_Price_7DS','Floor_Price_7DS']].values[0]
                    c2, f2 = df.loc[df['Match_ID']==rev, ['Ceiling_Price_7DS','Floor_Price_7DS']].values[0]
                    final_val = min(max(unified, min(f1, f2)), max(c1, c2))
                    final_prices_7ds[mid] = final_prices_7ds[rev] = float(final_val)
            df['New_7DS'] = df['Match_ID'].map(final_prices_7ds)
            # IMPORTANT: Save this heavy calculated result to Session State memory
            st.session_state["optimized_df"] = df.copy()
            st.session_state["network_adj"] = adj

        # Safely load the static data out of the application memory bank
        df = st.session_state["optimized_df"].copy()
        adj = st.session_state["network_adj"]

        # --- POPULATE OUTPUT METRICS AND YIELDS ---
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
            
            # Create price dictionary mappings for both underlying logic tables
            sdr_prices = df.set_index('Match_ID')['New_SDR'].to_dict()
            seasons_prices = df.set_index('Match_ID')['New_7DS'].to_dict()
            f_prices_new = df.set_index('Match_ID')['Display_New_Fare'].to_dict()
            f_prices_old = df.set_index('Match_ID')['Display_Original_Fare'].to_dict()
            
            # Establish alternating matching product configurations
            if chosen_ticket in ["SDR", "CDR"]:
                alt_product = "CDR"
                alt_label = "CDR (Cheap Day Return)"
            elif chosen_ticket in ["SDS", "CDS"]:
                alt_product = "CDS"
                alt_label = "CDS (Cheap Day Single)"
            else:
                alt_product = chosen_ticket
                alt_label = chosen_ticket
        
            start_clean = start_stn.replace(" ", "")
            end_clean = end_stn.replace(" ", "")
            
            direct_fare_id = f"{start_clean}-{end_clean}"
            direct_fare_new = f_prices_new.get(direct_fare_id, 0.0)
            
            # --- GATHER DATA FOR MULTI-PRODUCT MIXED SPLIT BAR CHART ---
            chart_data_splits = []
            for i in range(1, len(active_route) - 1):
                mid_stn = active_route[i]
                mid_clean = mid_stn.replace(" ", "")
                
                leg1_id = f"{start_clean}-{mid_clean}"
                leg2_id = f"{mid_clean}-{end_clean}"
                
                if chosen_ticket == "7DS":
                    # Separate pipeline handling 7DS weekly season rules exclusively
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
                    # Fetch base optimized SDR value to accurately apply product variation rules
                    base_sdr_l1 = sdr_prices.get(leg1_id, 0.0)
                    base_sdr_l2 = sdr_prices.get(leg2_id, 0.0)
                    
                    if base_sdr_l1 > 0 and base_sdr_l2 > 0:
                        l1_primary = derive_fare(base_sdr_l1, chosen_ticket)
                        l2_primary = derive_fare(base_sdr_l2, chosen_ticket)
                        
                        l1_alt = derive_fare(base_sdr_l1, alt_product)
                        l2_alt = derive_fare(base_sdr_l2, alt_product)
                        
                        pure_split = l1_primary + l2_primary
                        mix_strategy_a = l1_primary + l2_alt
                        mix_strategy_b = l1_alt + l2_primary
                        
                        chart_data_splits.append({
                            "Intermediate Station": mid_stn.title(),
                            "Pure Split": pure_split,
                            "Pure L1": l1_primary, "Pure L2": l2_primary,
                            "Mix A": mix_strategy_a,
                            "Mix A L1": l1_primary, "Mix A L2": l2_alt,
                            "Mix B": mix_strategy_b,
                            "Mix B L1": l1_alt, "Mix B L2": l2_primary
                        })

            # --- GATHER DATA FOR OLD VS NEW LINE COMPARATOR ---
            chart_data_comparison = []
            
            # Map exact raw values from spreadsheet columns directly to dictionaries
            raw_sds_old_map = df.set_index('Match_ID')['Original_SDS'].to_dict()
            raw_cds_old_map = df.set_index('Match_ID')['Original_CDS'].to_dict()
            raw_sdr_old_map = df.set_index('Match_ID')['Original_SDR'].to_dict()
            raw_cdr_old_map = df.set_index('Match_ID')['Original_CDR'].to_dict()
            raw_7ds_old_map = df.set_index('Match_ID')['Original_7DS'].to_dict()
            f_prices_sop = df.set_index('Match_ID')['Old_Super_OffPeak'].to_dict() # Map SOP fares
            
            for stn in active_route[1:]:
                stn_clean = stn.replace(" ", "")
                flow_id = f"{start_clean}-{stn_clean}"
                
                new_f = f_prices_new.get(flow_id, 0.0)
                sop_f = f_prices_sop.get(flow_id, 0.0)
                
                # Directly pull what the ticket fare is TODAY from its dedicated Excel column map
                if chosen_ticket == "SDS":
                    today_f = raw_sds_old_map.get(flow_id, 0.0)
                elif chosen_ticket == "CDS":
                    today_f = raw_cds_old_map.get(flow_id, 0.0)
                elif chosen_ticket == "SDR":
                    today_f = raw_sdr_old_map.get(flow_id, 0.0)
                elif chosen_ticket == "CDR":
                    today_f = raw_cdr_old_map.get(flow_id, 0.0)
                elif chosen_ticket == "7DS":
                    today_f = raw_7ds_old_map.get(flow_id, 0.0)
                else:
                    today_f = 0.0
                
                if today_f > 0 or new_f > 0:
                    chart_data_comparison.append({
                        "Station": stn.title(),
                        # SMART FIX: If today's fare is 0, store it as None so the graph skips it
                        "Old Fare (£)": today_f if today_f > 0 else None,
                        "New Fare (£)": new_f,
                        "Old Super Off-Peak (£)": sop_f if sop_f > 0 else None,
                        # If there was no historical fare, variance is blank/None instead of misleading
                        "Change (£)": round(new_f - today_f, 2) if today_f > 0 else None
                    })

           # 🟢 INITIALIZE TABS FOR DASHBOARD SEGREGATION
            tab1, tab2 = st.tabs(["📊 Hub Analytics", "🔍 Market Opportunities"])

            # 🟢 START OF TAB 1 CONTENTS (Analytics & Top 10 Tables)
            with tab1:
                gc1, gc2 = st.columns(2)
                
                with gc1:
                    if chart_data_splits and direct_fare_new > 0:
                        df_splits = pd.DataFrame(chart_data_splits)
                        fig_splits = go.Figure()
                        
                        # Track 1: Pure Splits (e.g., 7DS + 7DS or SDR + SDR)
                        fig_splits.add_trace(go.Bar(
                            x=df_splits["Intermediate Station"], y=df_splits["Pure Split"],
                            name=f"Pure Split ({chosen_ticket} + {chosen_ticket})", 
                            marker_color='rgb(55, 83, 109)',
                            customdata=df_splits[["Pure L1", "Pure L2"]],
                            hovertemplate="<b>Split Station: %{x}</b><br>Total Split Cost: £%{y:.2f}<br>Leg 1 ("+chosen_ticket+"): £%{customdata[0]:.2f}<br>Leg 2 ("+chosen_ticket+"): £%{customdata[1]:.2f}<extra></extra>"
                        ))
                        
                        # Only add Mixed Product combos if dealing with walk-up tickers (skip season passes)
                        if chosen_ticket != "7DS" and chosen_ticket != alt_product:
                            # Track 2: Product Mixture Combo A
                            fig_splits.add_trace(go.Bar(
                                x=df_splits["Intermediate Station"], y=df_splits["Mix A"],
                                name=f"Mixed Combo A ({chosen_ticket} + {alt_product})", 
                                marker_color='rgb(26, 118, 141)',
                                customdata=df_splits[["Mix A L1", "Mix A L2"]],
                                hovertemplate="<b>Split Station: %{x}</b><br>Total Split Cost: £%{y:.2f}<br>Leg 1 ("+chosen_ticket+"): £%{customdata[0]:.2f}<br>Leg 2 ("+alt_product+"): £%{customdata[1]:.2f}<extra></extra>"
                            ))
                            
                            # Track 3: Product Mixture Combo B
                            fig_splits.add_trace(go.Bar(
                                x=df_splits["Intermediate Station"], y=df_splits["Mix B"],
                                name=f"Mixed Combo B ({alt_product} + {chosen_ticket})", 
                                marker_color='rgb(158, 201, 225)',
                                customdata=df_splits[["Mix B L1", "Mix B L2"]],
                                hovertemplate="<b>Split Station: %{x}</b><br>Total Split Cost: £%{y:.2f}<br>Leg 1 ("+alt_product+"): £%{customdata[1]:.2f}<br>Leg 2 ("+chosen_ticket+"): £%{customdata[1]:.2f}<extra></extra>"
                            ))
                        
                        # Fixed baseline horizontal benchmark line representing the Direct selection fare
                        fig_splits.add_shape(
                            type="line", x0=-0.5, y0=direct_fare_new, x1=len(df_splits) - 0.5, y1=direct_fare_new,
                            line=dict(color="Crimson", width=3, dash="dash"),
                        )
                        
                        fig_splits.add_trace(go.Scatter(
                            x=[df_splits["Intermediate Station"].iloc[0]], y=[direct_fare_new],
                            mode="lines", name=f"Direct {chosen_ticket} Fare (£{direct_fare_new:.2f})",
                            line=dict(color="Crimson", width=3, dash="dash"), showlegend=True
                        ))
                        
                        fig_splits.update_layout(
                            title=f"{chosen_ticket} Split & Product Mix Check: {start_stn.title()} to {end_stn.title()}",
                            xaxis_title="Intermediate Splitting Points", yaxis_title="Total Fare Price (£)",
                            barmode='group', template="plotly_white", 
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        st.plotly_chart(fig_splits, use_container_width=True)
                    else:
                        st.info(f"No internal split points with complete fare combinations found for {chosen_ticket} tickets along this segment.")
                
                with gc2:
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

            # 🟢 START OF TAB 2 CONTENTS (Market Opportunities & Top 10 Tables)
            with tab2:
                
                # =========================================================================
                # --- TOP AGGREGATIONS AND METRICS TABLES ---
                # =========================================================================
                r2c1, r2c2 = st.columns(2)
                with r2c1:
                    st.subheader(f"Top 10 Price Increases ({chosen_ticket})")
                    st.dataframe(df.sort_values('Opt_Increase', ascending=False).head(10)[['Origin Description', 'Destination Description', 'Display_Original_Fare', 'Display_New_Fare', 'Opt_Increase']], 
                                 column_config={"Display_Original_Fare": st.column_config.NumberColumn("Baseline", format="£%.2f"), "Display_New_Fare": st.column_config.NumberColumn("New Fare", format="£%.2f"), "Opt_Increase": st.column_config.NumberColumn("Increase", format="£%.2f")}, 
                                 use_container_width=True, hide_index=True)
                with r2c2:
                    st.subheader(f"Top 10 Price Decreases ({chosen_ticket})")
                    dec_disp = df.sort_values('Diff', ascending=True).head(10).copy()
                    dec_disp['Diff'] = dec_disp['Diff'].abs()
                    st.dataframe(dec_disp[['Origin Description', 'Destination Description', 'Display_Original_Fare', 'Display_New_Fare', 'Diff']], 
                                 column_config={"Display_Original_Fare": st.column_config.NumberColumn("Original", format="£%.2f"), "Display_New_Fare": st.column_config.NumberColumn("New Fare", format="£%.2f"), "Diff": st.column_config.NumberColumn("Decrease", format="-£%.2f")}, 
                                 use_container_width=True, hide_index=True)

                # =========================================================================
                # --- BOTTOM ANOMALY OPPORTUNITIES ---
                # =========================================================================
                st.divider()
                r2c3, r2c4 = st.columns(2)
                with r2c3:
                    st.subheader("Remaining Split-Ticketing Opportunities")
                    f_prices = df.set_index('Match_ID')['Display_New_Fare'].to_dict()
                    base_prices = df.set_index('Match_ID')['Display_Original_Fare'].to_dict()
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
                                        gaps.append({
                                            "Journey": f"{str(n_map.get(A, A)).title()} to {str(n_map.get(C, C)).title()}", 
                                            "Split At": str(n_map.get(B, B)).title(), 
                                            "New Fare": thru, "Split Fare": s_sum, "Difference": round(thru - s_sum, 2)
                                        })
                    if gaps:
                        st.dataframe(pd.DataFrame(gaps).sort_values('Difference', ascending=False).head(300), 
                                     column_config={"New Fare": st.column_config.NumberColumn(format="£%.2f"), "Split Fare": st.column_config.NumberColumn(format="£%.2f"), "Difference": st.column_config.NumberColumn(format="£%.2f")},
                                     use_container_width=True, hide_index=True)
                    else:
                        st.success("No Split-Ticket Opportunities Found")
                         
                    split_before = 0
                    for A in adj:
                        for B in adj[A]:
                            if B not in adj: continue
                            for C in adj[B]:
                                id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                                if id_ac in base_prices:
                                    thru = base_prices[id_ac]
                                    s_sum = base_prices[id_ab] + base_prices.get(id_bc, 0)
                                    if thru > s_sum + 0.01: split_before += 1
        
                    split_after = len(gaps)
                    st.markdown(f"**Split-ticket opportunities solved:** {split_before - split_after}<br>**Remaining:** {split_after}", unsafe_allow_html=True)
                    
                with r2c4:
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
                                        near, far = f_prices[id_sn], f_prices[id_sf]
                                        if near > far + 0.01:
                                            lb_gaps.append({
                                                "Origin(A)": path[i].title(), "Destination(B)": path[j].title(), "Following Stn(C)": path[k].title(),
                                                "Price to B": near, "Price to C": far, "Difference": round(near - far, 2)
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
                                        if base_prices[id_sn] > base_prices[id_sf] + 0.01: lb_before += 1
                    lb_after = len(lb_gaps)
                    st.markdown(f"**Long-buying opportunities solved:** {lb_before - lb_after}<br>**Remaining:** {lb_after}", unsafe_allow_html=True)

        # 🟢 FALL BACK OUT OF TABS STRUCTURE FOR MAIN SUMMARY BASE
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

        st.divider()
        st.subheader("Full Context Fare Summary")
        
        output_df = df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Display_Original_Fare', 'Display_New_Fare', 'Status']].copy()
        st.dataframe(output_df, column_config={
            "Original_SDR": st.column_config.NumberColumn("Base Orig SDR", format="£%.2f"), 
            "New_SDR": st.column_config.NumberColumn("Base New SDR", format="£%.2f"),
            "Display_Original_Fare": st.column_config.NumberColumn(f"Orig {chosen_ticket}", format="£%.2f"),
            "Display_New_Fare": st.column_config.NumberColumn(f"New {chosen_ticket}", format="£%.2f")
        }, use_container_width=True, hide_index=True)
            
        st.download_button("Download Configured Fares", convert_df_to_csv(df), "Optimised_Network_Fares.csv", "text/csv")
else:
    # If the user drops a new file or clears current selections, wipe out cached results
    if "optimized_df" in st.session_state:
        del st.session_state["optimized_df"]
    st.info("Please upload fare spreadsheets in the sidebar to populate the dynamic optimization model dashboard.")
