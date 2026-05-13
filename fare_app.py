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
    st.caption("Turbo Edition: Optimized for Large Datasets")

# --- 1. SEQUENCES (Fixed Typos) ---
SEQUENCES = {
    "Reading-Aldershot": ["READING", "EARLEY", "WINNERSH TRIANGLE", "WINNERSH", "WOKINGHAM", "BRACKNELL", "MARTINS HERON", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "FARNHAM", "BENTLEY", "ALTON"],
    "Ascot-Ashtead": ["ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "ASHTEAD"],
    "Leatherhead-Dorking": ["LEATHERHEAD", "BOX HILL & WESTHUMBLE", "DORKING"],
    "London-Inbound": ["ZONE R1256 LONDON", "LONDON BR", "QUEENSTOWN ROAD (BATTERSEA)", "CLAPHAM JUNCTION LONDON", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT"],
    "Bagshot-Addlestone": ["ADDLESTONE", "CHERTSEY", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT"],
    "Aldershot-Oxshott-via-Surbiton": ["ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "HINCHLEY WOOD", "CLAYGATE", "OXSHOTT"],
    "Alton Main Line": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION", "QUEENSTOWN ROAD (BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Guildford-Hinchley Wood-via-Clandon": ["GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "COBHAM & STOKE D'ABERNON", "OXSHOTT", "CLAYGATE", "HINCHLEY WOOD"],
    "Ash-Chertsey": ["ASH", "WANBOROUGH", "GUILDFORD", "WORPLESDON", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "ADDLESTONE", "CHERTSEY"]
}

def round_up(x, base):
    if pd.isna(x) or x == 0: return 0
    if base == 0: return round(float(x), 2)
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
sdr_rounding = st.sidebar.select_slider("Rounding (£)", options=[0.00, 0.05, 0.10, 0.20, 0.50, 1.00], value=0.20)

uploaded_files = st.sidebar.file_uploader("Upload Fare Spreadsheets", type=["xlsx"], accept_multiple_files=True)

# --- 3. PROCESSING ---
if uploaded_files:
    with st.spinner("Processing Large Dataset..."):
        all_dfs = [pd.read_excel(f, sheet_name='Main Sheet', header=1) for f in uploaded_files]
        df = pd.concat(all_dfs, ignore_index=True)
        df.columns = [str(c).strip() for c in df.columns]
        
        df['Origin_N'] = df.iloc[:, 1].astype(str).str.upper().str.strip()
        df['Dest_N'] = df.iloc[:, 3].astype(str).str.upper().str.strip()
        df['Match_ID'] = df['Origin_N'].str.replace(" ", "") + "-" + df['Dest_N'].str.replace(" ", "")
        df['Original_SDR'] = pd.to_numeric(df.iloc[:, 9], errors='coerce').fillna(0)
        
        df = df.sort_values('Original_SDR', ascending=False).drop_duplicates(subset=['Match_ID']).copy()
        
        # Create indexed lookups for speed
        price_map = df.set_index('Match_ID')['Original_SDR'].to_dict()
        
        # Logic for "Foundation Price"
        def get_found(row):
            parts = row['Match_ID'].split("-")
            rev = f"{parts[1]}-{parts[0]}"
            max_p = max(row['Original_SDR'], price_map.get(rev, row['Original_SDR']))
            return round_up(max_p, sdr_rounding)

        df['New_SDR'] = df.apply(get_found, axis=1)
        df['Ceiling_Price'] = (df['Original_SDR'] * (1 + inc_cap)).apply(lambda x: round_up(x, sdr_rounding))
        df['Floor_Price'] = (df['Original_SDR'] * (1 - dec_cap)).apply(lambda x: round_up(x, sdr_rounding))
        df['Base_Price'] = df['New_SDR'].copy()

        # --- 4. THE SPEED OPTIMIZATION (Graph Mapping) ---
        # Map out which stations connect to what to avoid 8 million iterations
        adj = defaultdict(list)
        for mid in price_map.keys():
            orig, dest = mid.split("-")
            adj[orig].append(dest)

        # Loop optimized
        for _ in range(2): # 2 passes is usually enough for convergence
            new_prices = df.set_index('Match_ID')['New_SDR'].to_dict()
            for A in adj:
                for B in adj[A]:
                    if B not in adj: continue
                    for C in adj[B]:
                        id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                        if id_ac in price_map:
                            s_sum = new_prices[id_ab] + new_prices[id_bc]
                            thru = new_prices[id_ac]
                            if s_sum < (thru - 0.01):
                                # Update logic
                                if id_bc not in excluded_splits:
                                    new_prices[id_bc] = min(round_up(new_prices[id_bc] + (thru - s_sum)/2, sdr_rounding), (price_map[id_bc]*(1+inc_cap)))
                                if id_ac not in excluded_splits:
                                    new_prices[id_ac] = max(round_up(new_prices[id_ab] + new_prices[id_bc], sdr_rounding), (price_map[id_ac]*(1-dec_cap)))
            
            # Write back to DF
            df['New_SDR'] = df['Match_ID'].map(new_prices)

        # Long-buy check (limited to defined sequences)
        for seq in SEQUENCES.values():
            for i, start in enumerate(seq):
                s_clean = start.replace(" ","")
                for j, mid in enumerate(seq[i+1:], i+1):
                    m_clean = mid.replace(" ","")
                    for k, end in enumerate(seq[j+1:], j+1):
                        e_clean = end.replace(" ","")
                        id_s, id_l = f"{s_clean}-{m_clean}", f"{s_clean}-{e_clean}"
                        if id_s in price_map and id_l in price_map:
                            p_s = df.loc[df['Match_ID']==id_s, 'New_SDR'].values[0]
                            p_l = df.loc[df['Match_ID']==id_l, 'New_SDR'].values[0]
                            if p_l < p_s and id_l not in excluded_longbuys:
                                ceil = df.loc[df['Match_ID']==id_l, 'Ceiling_Price'].values[0]
                                df.loc[df['Match_ID']==id_l, 'New_SDR'] = min(p_s, ceil)

    # --- UI DISPLAY ---
    df['Diff'] = df['New_SDR'] - df['Original_SDR']
    df['Opt_Increase'] = df['New_SDR'] - df['Base_Price']
    df['Status'] = df['Diff'].apply(lambda x: "Increased" if x > 0.01 else ("Decreased" if x < -0.01 else "Unchanged"))

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top 10 Price Increases")
        st.dataframe(df.sort_values('Opt_Increase', ascending=False).head(10)[['Origin Description', 'Destination Description', 'Base_Price', 'New_SDR', 'Opt_Increase']], use_container_width=True, hide_index=True)
    with c2:
        st.subheader("Top 10 Price Decreases")
        dec_disp = df.sort_values('Diff', ascending=True).head(10).copy()
        dec_disp['Diff'] = dec_disp['Diff'].abs()
        st.dataframe(dec_disp[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Diff']], use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Full Summary")
    st.dataframe(df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Status']], use_container_width=True, hide_index=True)
    
    st.download_button("Download New Fares", convert_df_to_csv(df), "Final_Fares.csv", "text/csv")
