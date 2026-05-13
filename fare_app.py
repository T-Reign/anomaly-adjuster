import streamlit as st
import pandas as pd
import math
import os
from collections import defaultdict

st.set_page_config(page_title="Anomaly Adjuster", layout="wide")

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
    st.caption("Version 3.0: Ironclad Rounding & Proper Case")

# --- 1. ROUNDING LOGIC ---
def round_up(x, base):
    """Always rounds UP to the next boundary (e.g., 30.01 -> 30.20)"""
    if pd.isna(x) or x <= 0: return 0.0
    if base < 0.01: return round(float(x), 2)
    # math.ceil handles the upward push
    return math.ceil(round(float(x), 2) * (1/base)) / (1/base)

# --- 2. SIDEBAR ---
st.sidebar.header("1. Exclusions")
raw_split_ex = st.sidebar.text_area("Split-Ticket Exclusions:", value="READING-EARLEY")
excluded_splits = {line.strip().upper().replace(" ", "") for line in raw_split_ex.split('\n') if "-" in line}

raw_lb_ex = st.sidebar.text_area("Long-Buy Exclusions:", value="ALDERSHOT-OXSHOTT")
excluded_longbuys = {line.strip().upper().replace(" ", "") for line in raw_lb_ex.split('\n') if "-" in line}

st.sidebar.header("2. Settings")
inc_cap = st.sidebar.slider("Max Increase (%)", 0, 70, 8) / 100
dec_cap = st.sidebar.slider("Max Decrease (%)", 0, 70, 5) / 100
sdr_rounding = st.sidebar.select_slider("Rounding (£)", options=[0.01, 0.05, 0.10, 0.20, 0.50, 1.00], value=0.20)

uploaded_files = st.sidebar.file_uploader("Upload Fare Spreadsheets", type=["xlsx"], accept_multiple_files=True)

# --- 3. PROCESSING ---
if uploaded_files:
    with st.spinner("Standardizing and Rounding..."):
        all_dfs = [pd.read_excel(f, sheet_name='Main Sheet', header=1) for f in uploaded_files]
        df = pd.concat(all_dfs, ignore_index=True)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Proper Case for UI
        df['Origin Description'] = df.iloc[:, 1].astype(str).str.title().str.strip()
        df['Destination Description'] = df.iloc[:, 3].astype(str).str.title().str.strip()
        
        # Match IDs for Logic
        df['Origin_N'] = df['Origin Description'].str.upper().str.replace(" ", "")
        df['Dest_N'] = df['Destination Description'].str.upper().str.replace(" ", "")
        df['Match_ID'] = df['Origin_N'] + "-" + df['Dest_N']
        
        # Capture Raw Price
        df['Original_SDR'] = pd.to_numeric(df.iloc[:, 9], errors='coerce').fillna(0.0)
        
        # Deduplicate
        df = df.sort_values('Original_SDR', ascending=False).drop_duplicates(subset=['Match_ID']).copy()
        
        # STEP 1: CREATE ROUNDED BASELINE
        raw_price_map = df.set_index('Match_ID')['Original_SDR'].to_dict()
        
        def standardize_and_round(row):
            parts = row['Match_ID'].split("-")
            rev_id = f"{parts[1]}-{parts[0]}"
            # Directional consistency: take highest of current or reverse
            highest_raw = max(row['Original_SDR'], raw_price_map.get(rev_id, 0))
            # FORCE ROUND UP IMMEDIATELY
            return round_up(highest_raw, sdr_rounding)

        df['New_SDR'] = df.apply(standardize_and_round, axis=1)
        df['Base_Price'] = df['New_SDR'].copy() # This is now the "Rounded Foundation"
        
        # Step 2: Establish Caps (Also Rounded)
        df['Ceiling_Price'] = (df['Original_SDR'] * (1 + inc_cap)).apply(lambda x: round_up(x, sdr_rounding))
        df['Floor_Price'] = (df['Original_SDR'] * (1 - dec_cap)).apply(lambda x: round_up(x, sdr_rounding))

        # STEP 3: OPTIMIZATION (Splits)
        adj = defaultdict(list)
        for mid in raw_price_map.keys():
            orig, dest = mid.split("-")
            adj[orig].append(dest)

        for _ in range(2):
            curr_prices = df.set_index('Match_ID')['New_SDR'].to_dict()
            for A in adj:
                for B in adj[A]:
                    if B not in adj: continue
                    for C in adj[B]:
                        id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                        if id_ac in curr_prices:
                            thru = curr_prices[id_ac]
                            split_sum = curr_prices[id_ab] + curr_prices.get(id_bc, 9999)
                            
                            if split_sum < (thru - 0.01):
                                # Fix BC
                                if id_bc in curr_prices and id_bc not in excluded_splits:
                                    pot_inc = round_up(curr_prices[id_bc] + (thru - split_sum)/2, sdr_rounding)
                                    curr_prices[id_bc] = min(pot_inc, df.loc[df['Match_ID']==id_bc, 'Ceiling_Price'].values[0])
                                # Fix AC
                                if id_ac not in excluded_splits:
                                    pot_dec = round_up(curr_prices[id_ab] + curr_prices[id_bc], sdr_rounding)
                                    curr_prices[id_ac] = max(pot_dec, df.loc[df['Match_ID']==id_ac, 'Floor_Price'].values[0])
            df['New_SDR'] = df['Match_ID'].map(curr_prices)

    # Final calculations for display
    df['Diff'] = df['New_SDR'] - df['Original_SDR']
    df['Status'] = df['Diff'].apply(lambda x: "Increased" if x > 0.01 else ("Decreased" if x < -0.01 else "Unchanged"))

    # --- UI DISPLAY ---
    st.divider()
    st.subheader("Results Summary")
    
    # We use column_config to force the £ display and ensure the numbers are treated as currency
    st.dataframe(
        df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Status']], 
        column_config={
            "Original_SDR": st.column_config.NumberColumn("Original Fare", format="£%.2f"),
            "New_SDR": st.column_config.NumberColumn("Adjusted Fare", format="£%.2f"),
        },
        use_container_width=True, 
        hide_index=True
    )
    
    st.download_button("Download Processed Fares", convert_df_to_csv(df), "Final_Fares.csv", "text/csv")
