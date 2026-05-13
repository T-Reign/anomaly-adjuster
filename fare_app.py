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
    st.caption("Final Build: Comprehensive Audit Tables & Proper Case Formatting")

# --- 1. SEQUENCES ---
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
    if pd.isna(x) or x <= 0: return 0.0
    if base < 0.01: return round(float(x), 2)
    multiplied = round(float(x), 2) * (1/base)
    rounded_up = math.ceil(round(multiplied, 7)) / (1/base)
    return round(rounded_up, 2)

# --- 2. SIDEBAR ---
st.sidebar.header("1. Split-Ticket Exclusions")
raw_split_ex = st.sidebar.text_area("Flows to exclude from adjustment:", value="READING-EARLEY")
excluded_splits = {line.strip().upper().replace(" ", "") for line in raw_split_ex.split('\n') if "-" in line}

st.sidebar.header("2. Long-Buy Exclusions")
raw_lb_ex = st.sidebar.text_area("Flows to exclude from adjustment:", value="ALDERSHOT-OXSHOTT")
excluded_longbuys = {line.strip().upper().replace(" ", "") for line in raw_lb_ex.split('\n') if "-" in line}

st.sidebar.header("1. Settings")
inc_cap = st.sidebar.slider("Maximum Increase (cap) (%)", 0, 70, 8) / 100
dec_cap = st.sidebar.slider("Maximum Decrease (cap) (%)", 0, 70, 5) / 100
sdr_rounding = st.sidebar.select_slider("Rounding (£)", options=[0.01, 0.05, 0.10, 0.20, 0.50, 1.00], value=0.20)

st.sidebar.header("2. Exclusions")
raw_split_ex = st.sidebar.text_area("Split-Ticket Exclusions:", value="READING-EARLEY")
excluded_splits = {line.strip().upper().replace(" ", "") for line in raw_split_ex.split('\n') if "-" in line}

uploaded_files = st.sidebar.file_uploader("Upload Fare Spreadsheets", type=["xlsx"], accept_multiple_files=True)

# --- 3. PROCESSING ---
if uploaded_files:
    with st.spinner("Calculating Optimized Network..."):
        all_dfs = [pd.read_excel(f, sheet_name='Main Sheet', header=1) for f in uploaded_files]
        df = pd.concat(all_dfs, ignore_index=True)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Proper Case Formatting for UI
        df['Origin Description'] = df.iloc[:, 1].astype(str).str.title().str.strip()
        df['Destination Description'] = df.iloc[:, 3].astype(str).str.title().str.strip()
        
        # Upper Case with No Spaces for Logic Match
        df['Origin_N'] = df['Origin Description'].str.upper().str.replace(" ", "")
        df['Dest_N'] = df['Destination Description'].str.upper().str.replace(" ", "")
        df['Match_ID'] = df['Origin_N'] + "-" + df['Dest_N']
        
        df['Original_SDR'] = pd.to_numeric(df.iloc[:, 9], errors='coerce').fillna(0.0)
        df = df.sort_values('Original_SDR', ascending=False).drop_duplicates(subset=['Match_ID']).copy()
        
        # 3.1 Standardization (Highest Directional Fare) & Baseline Rounding
        raw_price_map = df.set_index('Match_ID')['Original_SDR'].to_dict()
        
        def initial_prep(row):
            parts = row['Match_ID'].split("-")
            rev_id = f"{parts[1]}-{parts[0]}"
            highest = max(row['Original_SDR'], raw_price_map.get(rev_id, 0))
            return round_up(highest, sdr_rounding)

        df['New_SDR'] = df.apply(initial_prep, axis=1)
        df['Base_Price'] = df['New_SDR'].copy()
        df['Ceiling_Price'] = (df['Original_SDR'] * (1 + inc_cap)).apply(lambda x: round_up(x, sdr_rounding))
        df['Floor_Price'] = (df['Original_SDR'] * (1 - dec_cap)).apply(lambda x: round_up(x, sdr_rounding))

        # 3.2 High-Speed Adjacency Map
        adj = defaultdict(list)
        for mid in raw_price_map.keys():
            o, d = mid.split("-")
            adj[o].append(d)

        # 3.3 The Optimization Loops (Now with Exclusions for both Splits & Long-Buys)
        for _ in range(2):
            curr = df.set_index('Match_ID')['New_SDR'].to_dict()
            
            # --- PART A: SPLIT FIXING ---
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
            
            # --- PART B: LONG-BUY FIXING (Uses your second sidebar list) ---
            for path in SEQUENCES.values():
                for i, s in enumerate(path):
                    for j, n in enumerate(path[i+1:], i+1):
                        for k, f in enumerate(path[j+1:], j+1):
                            id_near = f"{s.replace(' ','')}-{n.replace(' ','')}"
                            id_far = f"{s.replace(' ','')}-{f.replace(' ','')}"
                            if id_near in curr and id_far in curr:
                                if curr[id_near] > curr[id_far]:
                                    if id_near not in excluded_longbuys:
                                        # Fix: reduce the 'Near' fare to match the 'Far' fare (within floor limits)
                                        curr[id_near] = max(curr[id_far], df.loc[df['Match_ID']==id_near, 'Floor_Price'].values[0])

            df['New_SDR'] = df['Match_ID'].map(curr)

    # Calculation for UI Display
    df['Diff'] = df['New_SDR'] - df['Original_SDR']
    df['Opt_Increase'] = df['New_SDR'] - df['Base_Price']
    df['Status'] = df['Diff'].apply(lambda x: "Increased" if x > 0.01 else ("Decreased" if x < -0.01 else "Unchanged"))

    # --- DASHBOARD ---
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
        st.subheader("Remaining Split Gaps")
        final_map = df.set_index('Match_ID')['New_SDR'].to_dict()
        name_map = df.set_index('Origin_N')['Origin Description'].to_dict()
        gaps = []
        for A in adj:
            for B in adj[A]:
                if B not in adj: continue
                for C in adj[B]:
                    id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                    if id_ac in final_map:
                        thru, s_sum = final_map[id_ac], final_map[id_ab] + final_map.get(id_bc, 0)
                        if thru > (s_sum + 0.01):
                            gaps.append({"Journey": f"{name_map.get(A, A)} to {name_map.get(C, C)}", "Split At": name_map.get(B, B), "New Fare": thru, "Split Fare": s_sum, "Gap": round(thru - s_sum, 2)})
        if gaps:
            st.dataframe(pd.DataFrame(gaps).sort_values('Gap', ascending=False).head(10), 
                         column_config={"New Fare": st.column_config.NumberColumn(format="£%.2f"), "Split Fare": st.column_config.NumberColumn(format="£%.2f"), "Gap": st.column_config.NumberColumn(format="£%.2f")},
                         use_container_width=True, hide_index=True)
        else:
            st.success("No Split Gaps Found!")

    with r2c2:
        st.subheader("Remaining Long-Buy Gaps")
        lb_gaps = []
        for path in SEQUENCES.values():
            for i, s in enumerate(path):
                s_c = s.replace(" ","")
                for j, n in enumerate(path[i+1:], i+1):
                    n_c = n.replace(" ","")
                    for k, f in enumerate(path[j+1:], j+1):
                        f_c = f.replace(" ","")
                        id_n, id_f = f"{s_c}-{n_c}", f"{s_c}-{f_c}"
                        if id_n in final_map and id_f in final_map:
                            if final_map[id_n] > final_map[id_f]:
                                lb_gaps.append({"Journey": f"{s.title()} to", "Dest": n.title(), "Price": final_map[id_n], "Cheaper Further": f.title(), "Gap": round(final_map[id_n] - final_map[id_f], 2)})
        if lb_gaps:
            st.dataframe(pd.DataFrame(lb_gaps).sort_values('Gap', ascending=False).head(10), 
                         column_config={"Price": st.column_config.NumberColumn(format="£%.2f"), "Gap": st.column_config.NumberColumn(format="£%.2f")},
                         use_container_width=True, hide_index=True)
        else:
            st.info("No Long-Buy Gaps Found!")

    st.divider()
    st.subheader("Full Fare Summary")
    st.dataframe(df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Status']], 
                 column_config={"Original_SDR": st.column_config.NumberColumn("Original", format="£%.2f"), "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f")},
                 use_container_width=True, hide_index=True)
    
    st.download_button("Download Final Quartz Fares", convert_df_to_csv(df), "Final_Quartz_Fares.csv", "text/csv")
