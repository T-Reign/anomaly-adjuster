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
    st.caption("Final Revision: Floating Point & Precision Fix")

# --- 1. THE ROUNDING ENGINE ---
def round_up(x, base):
    """Strict Round Up with floating point protection"""
    if pd.isna(x) or x <= 0: return 0.0
    if base < 0.01: return round(float(x), 2)
    # The 1e-9 is a 'epsilon' to prevent 30.20 being rounded to 30.40 due to tiny computer errors
    multiplied = round(float(x), 2) * (1/base)
    rounded_up = math.ceil(round(multiplied, 7)) / (1/base)
    return round(rounded_up, 2)

# --- 2. SEQUENCES ---
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

# --- 3. SIDEBAR ---
st.sidebar.header("1. Settings")
inc_cap = st.sidebar.slider("Max Increase (%)", 0, 70, 8) / 100
dec_cap = st.sidebar.slider("Max Decrease (%)", 0, 70, 5) / 100
sdr_rounding = st.sidebar.select_slider("Rounding (£)", options=[0.01, 0.05, 0.10, 0.20, 0.50, 1.00], value=0.20)

raw_split_ex = st.sidebar.text_area("Split-Ticket Exclusions (ID format):", value="READING-EARLEY")
excluded_splits = {line.strip().upper().replace(" ", "") for line in raw_split_ex.split('\n') if "-" in line}

uploaded_files = st.sidebar.file_uploader("Upload Fare Spreadsheets", type=["xlsx"], accept_multiple_files=True)

# --- 4. PROCESSING ---
if uploaded_files:
    with st.spinner("Calculating..."):
        all_dfs = [pd.read_excel(f, sheet_name='Main Sheet', header=1) for f in uploaded_files]
        df = pd.concat(all_dfs, ignore_index=True)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Format Descriptions
        df['Origin Description'] = df.iloc[:, 1].astype(str).str.title().str.strip()
        df['Destination Description'] = df.iloc[:, 3].astype(str).str.title().str.strip()
        df['Match_ID'] = df['Origin Description'].str.upper().str.replace(" ", "") + "-" + df['Destination Description'].str.upper().str.replace(" ", "")
        
        # Get Prices
        df['Original_SDR'] = pd.to_numeric(df.iloc[:, 9], errors='coerce').fillna(0.0)
        df = df.sort_values('Original_SDR', ascending=False).drop_duplicates(subset=['Match_ID']).copy()
        
        # 4.1 Directional Consistency & Rounding-First
        raw_price_map = df.set_index('Match_ID')['Original_SDR'].to_dict()
        
        def initial_clean(row):
            parts = row['Match_ID'].split("-")
            rev_id = f"{parts[1]}-{parts[0]}"
            highest = max(row['Original_SDR'], raw_price_map.get(rev_id, 0))
            return round_up(highest, sdr_rounding)

        df['New_SDR'] = df.apply(initial_clean, axis=1)
        df['Ceiling_Price'] = (df['Original_SDR'] * (1 + inc_cap)).apply(lambda x: round_up(x, sdr_rounding))
        df['Floor_Price'] = (df['Original_SDR'] * (1 - dec_cap)).apply(lambda x: round_up(x, sdr_rounding))

        # 4.2 Optimization
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
                            thru = curr[id_ac]
                            split_sum = curr[id_ab] + curr.get(id_bc, 9999)
                            if split_sum < (thru - 0.009): # Tolerance for float
                                if id_bc in curr and id_bc not in excluded_splits:
                                    pot_inc = round_up(curr[id_bc] + (thru - split_sum)/2, sdr_rounding)
                                    curr[id_bc] = min(pot_inc, df.loc[df['Match_ID']==id_bc, 'Ceiling_Price'].values[0])
                                if id_ac not in excluded_splits:
                                    pot_dec = round_up(curr[id_ab] + curr[id_bc], sdr_rounding)
                                    curr[id_ac] = max(pot_dec, df.loc[df['Match_ID']==id_ac, 'Floor_Price'].values[0])
            df['New_SDR'] = df['Match_ID'].map(curr)

    # 4.3 Final Audit Tables
    st.divider()
    col_a, col_b = st.columns(2)
    
    # Remaining Splits Audit
    with col_a:
        st.subheader("Remaining Split Gaps")
        final_map = df.set_index('Match_ID')['New_SDR'].to_dict()
        name_map = df.set_index('Match_ID')['Origin Description'].to_dict() # Fallback name map
        gaps = []
        for A in adj:
            for B in adj[A]:
                if B not in adj: continue
                for C in adj[B]:
                    id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                    if id_ac in final_map:
                        thru, s_sum = final_map[id_ac], final_map[id_ab] + final_map.get(id_bc, 0)
                        if thru > (s_sum + 0.01):
                            gaps.append({"Journey": f"{A} to {C}", "Split": B, "Gap": round(thru - s_sum, 2)})
        if gaps:
            st.dataframe(pd.DataFrame(gaps).sort_values('Gap', ascending=False).head(10), use_container_width=True)
        else:
            st.success("No Split Gaps!")

    # Remaining Long-Buy Audit
    with col_b:
        st.subheader("Remaining Long-Buy Gaps")
        lb_gaps = []
        for path in SEQUENCES.values():
            for i, s in enumerate(path):
                for j, n in enumerate(path[i+1:], i+1):
                    for k, f in enumerate(path[j+1:], j+1):
                        id_n, id_f = f"{s.replace(' ','')}-{n.replace(' ','')}", f"{s.replace(' ','')}-{f.replace(' ','')}"
                        if id_n in final_map and id_f in final_map:
                            if final_map[id_n] > final_map[id_f]:
                                lb_gaps.append({"From": s, "To": n, "Price": final_map[id_n], "Further": f, "Price_F": final_map[id_f]})
        if lb_gaps:
            st.dataframe(pd.DataFrame(lb_gaps).head(10), use_container_width=True)
        else:
            st.info("No Long-Buy Gaps!")

    st.divider()
    st.subheader("Full Fare List")
    st.dataframe(
        df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR']], 
        column_config={
            "Original_SDR": st.column_config.NumberColumn("Original", format="£%.2f"),
            "New_SDR": st.column_config.NumberColumn("New", format="£%.2f"),
        },
        use_container_width=True, hide_index=True
    )
    
    st.download_button("Download Final CSV", convert_df_to_csv(df), "Processed_Fares.csv")
