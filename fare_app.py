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
    st.caption("Final Build: Proper Case, Strict Rounding & Turbo Speed")

# --- 1. SEQUENCES ---
# Paste your 20+ routes here.
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
    return math.ceil(round(float(x), 2) * (1/base)) / (1/base)

# --- 2. SIDEBAR ---
st.sidebar.header("1. Split-Ticket Exclusions")
raw_split_ex = st.sidebar.text_area("Flows to exclude from adjustment:", value="READING-EARLEY")
excluded_splits = {line.strip().upper().replace(" ", "") for line in raw_split_ex.split('\n') if "-" in line}

st.sidebar.header("2. Long-Buy Exclusions")
raw_lb_ex = st.sidebar.text_area("Flows to exclude from adjustment:", value="ALDERSHOT-OXSHOTT")
excluded_longbuys = {line.strip().upper().replace(" ", "") for line in raw_lb_ex.split('\n') if "-" in line}

st.sidebar.header("3. Optimisation Settings")
inc_cap = st.sidebar.slider("Maximum Increase (cap) (%)", 0, 70, 8) / 100
dec_cap = st.sidebar.slider("Maximum Decrease (cap) (%)", 0, 70, 5) / 100
sdr_rounding = st.sidebar.select_slider("Rounding (£)", options=[0.00, 0.05, 0.10, 0.20, 0.50, 1.00], value=0.20)

uploaded_files = st.sidebar.file_uploader("Upload Fare Spreadsheets", type=["xlsx"], accept_multiple_files=True)

# --- 3. PROCESSING ---
if uploaded_files:
    with st.spinner("Processing Network..."):
        all_dfs = [pd.read_excel(f, sheet_name='Main Sheet', header=1) for f in uploaded_files]
        raw_df = pd.concat(all_dfs, ignore_index=True)
        raw_df.columns = [str(c).strip() for c in raw_df.columns]
        
        # Formatting: Proper Case for UI, Upper for Logic
        raw_df['Origin Description'] = raw_df.iloc[:, 1].astype(str).str.title().str.strip()
        raw_df['Destination Description'] = raw_df.iloc[:, 3].astype(str).str.title().str.strip()
        
        raw_df['Origin_N'] = raw_df['Origin Description'].str.upper().str.replace(" ", "")
        raw_df['Dest_N'] = raw_df['Destination Description'].str.upper().str.replace(" ", "")
        raw_df['Match_ID'] = raw_df['Origin_N'] + "-" + raw_df['Dest_N']
        raw_df['Original_SDR'] = pd.to_numeric(raw_df.iloc[:, 9], errors='coerce').fillna(0)
        
        df = raw_df.sort_values('Original_SDR', ascending=False).drop_duplicates(subset=['Match_ID']).copy()
        price_map = df.set_index('Match_ID')['Original_SDR'].to_dict()
        
        # Foundation price (highest of return/reverse)
        def get_found_price(row):
            parts = row['Match_ID'].split("-")
            rev = f"{parts[1]}-{parts[0]}"
            m_p = max(row['Original_SDR'], price_map.get(rev, row['Original_SDR']))
            return round_up(m_p, sdr_rounding)

        df['New_SDR'] = df.apply(get_found_price, axis=1)
        df['Ceiling_Price'] = (df['Original_SDR'] * (1 + inc_cap)).apply(lambda x: round_up(x, sdr_rounding))
        df['Floor_Price'] = (df['Original_SDR'] * (1 - dec_cap)).apply(lambda x: round_up(x, sdr_rounding))
        df['Base_Price'] = df['New_SDR'].copy()

        # Build Adjacency Map
        adj = defaultdict(list)
        for mid in price_map.keys():
            orig, dest = mid.split("-")
            adj[orig].append(dest)

        # Optimization Loops
        for _ in range(2):
            curr_prices = df.set_index('Match_ID')['New_SDR'].to_dict()
            for A in adj:
                for B in adj[A]:
                    if B not in adj: continue
                    for C in adj[B]:
                        id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                        if id_ac in price_map:
                            s_sum = curr_prices[id_ab] + curr_prices[id_bc]
                            thru = curr_prices[id_ac]
                            if s_sum < (thru - 0.01):
                                if id_bc not in excluded_splits:
                                    pot_inc = round_up(curr_prices[id_bc] + (thru - s_sum)/2, sdr_rounding)
                                    curr_prices[id_bc] = min(pot_inc, (price_map[id_bc] * (1 + inc_cap)))
                                if id_ac not in excluded_splits:
                                    pot_dec = round_up(curr_prices[id_ab] + curr_prices[id_bc], sdr_rounding)
                                    curr_prices[id_ac] = max(pot_dec, (price_map[id_ac] * (1 - dec_cap)))
            df['New_SDR'] = df['Match_ID'].map(curr_prices)

    df['Diff'] = df['New_SDR'] - df['Original_SDR']
    df['Opt_Increase'] = df['New_SDR'] - df['Base_Price']
    df['Status'] = df['Diff'].apply(lambda x: "Increased" if x > 0.01 else ("Decreased" if x < -0.01 else "Unchanged"))

    # --- DASHBOARD ---
    st.divider()
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.subheader("Top 10 Price Increases")
        st.dataframe(df.sort_values('Opt_Increase', ascending=False).head(10)[['Origin Description', 'Destination Description', 'Base_Price', 'New_SDR', 'Opt_Increase']], 
                     column_config={"Base_Price": st.column_config.NumberColumn("Base Fare", format="£%.2f"), "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f"), "Opt_Increase": st.column_config.NumberColumn("Increase", format="£%.2f")}, 
                     use_container_width=True, hide_index=True)
    with r1c2:
        st.subheader("Top 10 Price Decreases")
        dec_disp = df.sort_values('Diff', ascending=True).head(10).copy()
        dec_disp['Diff'] = dec_disp['Diff'].abs()
        st.dataframe(dec_disp[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Diff']], 
                     column_config={"Original_SDR": st.column_config.NumberColumn("Base Fare", format="£%.2f"), "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f"), "Diff": st.column_config.NumberColumn("Decrease", format="£%.2f")}, 
                     use_container_width=True, hide_index=True)

    st.divider()
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.subheader("Remaining Split Opportunities")
        split_gaps = []
        final_prices = df.set_index('Match_ID')['New_SDR'].to_dict()
        name_map = df.set_index('Origin_N')['Origin Description'].to_dict()
        
        for A in adj:
            for B in adj[A]:
                if B not in adj: continue
                for C in adj[B]:
                    id_ac, id_ab, id_bc = f"{A}-{C}", f"{A}-{B}", f"{B}-{C}"
                    if id_ac in price_map:
                        thru_p, split_p = final_prices[id_ac], final_prices[id_ab] + final_prices[id_bc]
                        if thru_p - split_p > 0.01:
                            split_gaps.append({"Journey": f"{name_map.get(A, A)} to {name_map.get(C, C)}", "Split At": name_map.get(B, B), "New Fare": thru_p, "Split Fare": split_p, "Difference": round(thru_p - split_p, 2)})
        if split_gaps:
            st.dataframe(pd.DataFrame(split_gaps).sort_values('Difference', ascending=False).head(10), 
                         column_config={"New Fare": st.column_config.NumberColumn("New Fare", format="£%.2f"), "Split Fare": st.column_config.NumberColumn("Split Fare", format="£%.2f"), "Difference": st.column_config.NumberColumn("Difference", format="£%.2f")},
                         use_container_width=True, hide_index=True)
        else:
            st.success("No split-ticket opportunities remaining")

    with r2c2:
        st.subheader("Remaining Long-Buying Opportunities")
        lb_gaps = []
        for seq_name, path in SEQUENCES.items():
            for i, start in enumerate(path):
                s_c = start.upper().replace(" ","")
                for j, near in enumerate(path[i+1:], i+1):
                    n_c = near.upper().replace(" ","")
                    for k, far in enumerate(path[j+1:], j+1):
                        f_c = far.upper().replace(" ","")
                        id_n, id_f = f"{s_c}-{n_c}", f"{s_c}-{f_c}"
                        if id_n in final_prices and id_f in final_prices:
                            p_n, p_f = final_prices[id_n], final_prices[id_f]
                            if p_n - p_f > 0.01:
                                lb_gaps.append({"Journey": f"{start.title()} to", "Destination": near.title(), "Higher than": far.title(), "By": round(p_n - p_f, 2)})
        if lb_gaps:
            st.dataframe(pd.DataFrame(lb_gaps).sort_values('By', ascending=False).head(10), 
                         column_config={"By": st.column_config.NumberColumn("By", format="£%.2f")},
                         use_container_width=True, hide_index=True)
        else:
            st.info("No long-buying opportunities remaining")

    st.divider()
    st.subheader("Full Summary")
    st.dataframe(df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Status']], 
                 column_config={"Original_SDR": st.column_config.NumberColumn("Base Fare", format="£%.2f"), "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f")},
                 use_container_width=True, hide_index=True)
    
    st.download_button("Download New Fares", convert_df_to_csv(df), "Final_Fares_ProperCase.csv", "text/csv")
