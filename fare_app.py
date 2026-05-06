import streamlit as st
import pandas as pd
import math
import os

st.set_page_config(page_title="Anomaly Adjuster", layout="wide")

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
    "Reading-Aldershot": ["READING", "EARLEY", "WINNERSH TRIANGLE", "WINNERSH", "WOKINGHAM", "BRACKNELL", "MARTINS HERON", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "FARNHAM", "BENTLEY", "ALTON"],
    "Ascot-Ashtead": ["ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "ASHTEAD"],
    "Leatherhead-Dorking": ["LEATHERHEAD", "BOX HILL & WESTHUMBLE", "DORKING"],
    "London-Inbound": ["ZONE R1256 LONDON", "LONDON BR", "QUEENSTOWN ROAD (BATTERSEA)", "CLAPHAM JUNCTION LONDON", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT"],
    "Bagshot-Addlestone": ["ADDLESTONE", "CHERTSEY", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT"],
    "Aldershot-Oxshott-via-Surbiton": ["ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "HINCHLEY WOOD", "CLAYGATE", "OXSHOTT"],
    "Alton Main Line": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION", "QUEENSTOWN ROAD (BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Aldershot-Hinchley Wood-via-Clandon": ["ALDERSHOT", "ASH VALE", "ASH", "WANBOROUGH", "GUILDFORD", "LONDDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "COBHAM & STOKE D'ABERNON", "OXSHOTT", "CLAYGATE", "HINCHLEY WOOD"],
    "Ash-Chertsey": ["ASH", "WANBOROUGH", "GUIDLFORD", "WORPLESDON", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "ADDLESTONE", "CHERTSEY"]
    
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
    all_dfs = []
    for file in uploaded_files:
        temp_df = pd.read_excel(file, sheet_name='Main Sheet', header=1)
        all_dfs.append(temp_df)
    
    raw_df = pd.concat(all_dfs, ignore_index=True)
    raw_df.columns = [str(c).strip() for c in raw_df.columns]
    
    raw_df['Origin_N'] = raw_df.iloc[:, 1].astype(str).str.upper().str.strip()
    raw_df['Dest_N'] = raw_df.iloc[:, 3].astype(str).str.upper().str.strip()
    raw_df['Match_ID'] = raw_df['Origin_N'].str.replace(" ", "") + "-" + raw_df['Dest_N'].str.replace(" ", "")
    raw_df['Original_SDR'] = raw_df.iloc[:, 9].astype(float)
    
    df = raw_df.sort_values('Original_SDR', ascending=False).drop_duplicates(subset=['Match_ID']).copy()
    price_lookup = df.set_index('Match_ID')['Original_SDR'].to_dict()
    
    def get_foundation_price(match_id, original_price):
        parts = match_id.split("-")
        reverse_id = f"{parts[1]}-{parts[0]}"
        max_orig = max(original_price, price_lookup.get(reverse_id, original_price))
        return round_up(max_orig, sdr_rounding)

    df['New_SDR'] = df.apply(lambda row: get_foundation_price(row['Match_ID'], row['Original_SDR']), axis=1)
    df['Ceiling_Price'] = (df['Original_SDR'] * (1 + inc_cap)).apply(lambda x: round_up(x, sdr_rounding))
    df['Floor_Price'] = (df['Original_SDR'] * (1 - dec_cap)).apply(lambda x: round_up(x, sdr_rounding))
    df['Base_Price'] = df['New_SDR'].copy() 

    # --- 4. LOOP ---
    all_stations = list(set(df['Origin_N'].unique()) | set(df['Dest_N'].unique()))
    for pass_num in range(4):
        for A in all_stations:
            for C in all_stations:
                match_ac = A.replace(" ", "") + "-" + C.replace(" ", "")
                if match_ac not in price_lookup: continue
                idx_ac = df[df['Match_ID'] == match_ac].index[0]
                for B in all_stations:
                    id_ab, id_bc = A.replace(" ", "") + "-" + B.replace(" ", ""), B.replace(" ", "") + "-" + C.replace(" ", "")
                    if id_ab in price_lookup and id_bc in price_lookup:
                        idx_ab, idx_bc = df[df['Match_ID'] == id_ab].index[0], df[df['Match_ID'] == id_bc].index[0]
                        split_sum = df.at[idx_ab, 'New_SDR'] + df.at[idx_bc, 'New_SDR']
                        through_fare = df.at[idx_ac, 'New_SDR']
                        if split_sum < (through_fare - 0.01):
                            if id_bc not in excluded_splits:
                                pot_inc = round_up(df.at[idx_bc, 'New_SDR'] + (through_fare - split_sum)/2, sdr_rounding)
                                df.at[idx_bc, 'New_SDR'] = min(pot_inc, df.at[idx_bc, 'Ceiling_Price'])
                            if match_ac not in excluded_splits:
                                pot_dec = round_up(df.at[idx_ab, 'New_SDR'] + df.at[idx_bc, 'New_SDR'], sdr_rounding)
                                df.at[idx_ac, 'New_SDR'] = max(pot_dec, df.at[idx_ac, 'Floor_Price'])

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
        # Fix: Show absolute value for 'Drop' to avoid £-2.50 formatting
        decreases_display = df.sort_values('Diff', ascending=True).head(10).copy()
        decreases_display['Diff'] = decreases_display['Diff'].abs()
        st.dataframe(decreases_display[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Diff']], 
                     column_config={
                         "Original_SDR": st.column_config.NumberColumn("Base Fare", format="£%.2f"), 
                         "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f"), 
                         "Diff": st.column_config.NumberColumn("Decrease", format="£%.2f")
                     }, 
                     use_container_width=True, hide_index=True)

    st.divider()
    r2c1, r2c2 = st.columns(2)
    
    with r2c1:
        st.subheader("Remaining Split Opportunities")
        split_gaps = []
        for A in all_stations:
            for C in all_stations:
                match_id = A.replace(" ", "") + "-" + C.replace(" ", "")
                if match_id not in price_lookup: continue
                thru_p = df[df['Match_ID'] == match_id]['New_SDR'].iloc[0]
                for B in all_stations:
                    id_ab, id_bc = A.replace(" ", "") + "-" + B.replace(" ", ""), B.replace(" ", "") + "-" + C.replace(" ", "")
                    if id_ab in price_lookup and id_bc in price_lookup:
                        split_p = df[df['Match_ID'] == id_ab]['New_SDR'].iloc[0] + df[df['Match_ID'] == id_bc]['New_SDR'].iloc[0]
                        if thru_p - split_p > 0.01:
                            split_gaps.append({"Journey": f"{A} to {C}", "New Fare": thru_p, "Split Fare": split_p, "Difference": round(thru_p - split_p, 2)})
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
            for i, start_st in enumerate(path):
                for j, near_st in enumerate(path[i+1:], i+1):
                    for k, far_st in enumerate(path[j+1:], j+1):
                        id_s, id_l = start_st.replace(" ", "") + "-" + near_st.replace(" ", ""), start_st.replace(" ", "") + "-" + far_st.replace(" ", "")
                        if id_s in price_lookup and id_l in price_lookup:
                            p_s, p_l = df[df['Match_ID'] == id_s]['New_SDR'].iloc[0], df[df['Match_ID'] == id_l]['New_SDR'].iloc[0]
                            if p_s - p_l > 0.01:
                                lb_gaps.append({"Journey": f"{start_st} to", "Destination": near_st, "Higher than (next stop)": far_st, "By": round(p_s - p_l, 2)})
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
    st.download_button("Download Unified CSV", df.to_csv(index=False), "v14_4_final.csv")
