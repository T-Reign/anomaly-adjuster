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
    "Reading-Aldershot": ["READING", "EARLEY", "WINNERSH TRIANGLE", "WINNERSH", "WOKINGHAM", "BRACKNELL", "MARTINS HERON", "ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "FARNHAM", "BENTLEY", "ALTON"],
    "Ascot-Ashtead": ["ASCOT", "BAGSHOT", "CAMBERLEY", "FRIMLEY", "ASH VALE", "ALDERSHOT", "ASH", "WANBOROUGH", "GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "BOOKHAM", "LEATHERHEAD", "ASHTEAD"],
    "Leatherhead-Dorking": ["LEATHERHEAD", "BOX HILL & WESTHUMBLE", "DORKING"],
    "London-Inbound": ["ZONE R1256 LONDON", "LONDON BR", "QUEENSTOWN ROAD(BATTERSEA)", "CLAPHAM JUNCTION LONDON", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT"],
    "Bagshot-Addlestone": ["ADDLESTONE", "CHERTSEY", "VIRGINIA WATER", "LONGCROSS", "SUNNINGDALE", "ASCOT", "BAGSHOT"],
    "Aldershot-Oxshott-via-Surbiton": ["ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "HINCHLEY WOOD", "CLAYGATE", "OXSHOTT"],
    "Alton Main Line": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"],
    "Guildford-Hinchley Wood-via-Clandon": ["GUILDFORD", "LONDON ROAD (GUILDFORD)", "CLANDON", "HORSLEY", "EFFINGHAM JUNCTION", "COBHAM & STOKE D'ABERNON", "OXSHOTT", "CLAYGATE", "HINCHLEY WOOD"],
    "Ash-Chertsey": ["ASH", "WANBOROUGH", "GUILDFORD", "WORPLESDON", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "ADDLESTONE", "CHERTSEY"]
}

# Strict Round-Up Logic (Protects against floating point errors)
def round_up(x, base):
    if pd.isna(x) or x <= 0: return 0.0
    if base < 0.01: return round(float(x), 2)
    multiplied = round(float(x), 2) * (1/base)
    rounded_up = math.ceil(round(multiplied, 7)) / (1/base)
    return round(rounded_up, 2)

# --- 2. SIDEBAR ---
st.sidebar.header("1. Split-Ticket Exclusions")
raw_split_ex = st.sidebar.text_area("Flows to exclude from split adjustment:", value="READING-EARLEY")
excluded_splits = {line.strip().upper().replace(" ", "") for line in raw_split_ex.split('\n') if "-" in line}

st.sidebar.header("2. Long-Buy Exclusions")
raw_lb_ex = st.sidebar.text_area("Flows to exclude from long-buy adjustment:", value="ALDERSHOT-OXSHOTT")
excluded_longbuys = {line.strip().upper().replace(" ", "") for line in raw_lb_ex.split('\n') if "-" in line}

st.sidebar.header("3. Optimisation Settings")
slp_enabled = st.sidebar.checkbox("Enable Single-Leg Pricing", value=True)
inc_cap = st.sidebar.slider("Maximum Increase (cap) (%)", 0, 70, 8) / 100
dec_cap = st.sidebar.slider("Maximum Decrease (cap) (%)", 0, 70, 5) / 100
sdr_rounding = st.sidebar.select_slider("Rounding (£)", options=[0.01, 0.05, 0.10, 0.20, 0.50, 1.00], value=0.20)

uploaded_files = st.sidebar.file_uploader("Upload Fare Spreadsheets", type=["xlsx"], accept_multiple_files=True)

# --- 3. PROCESSING ---
if uploaded_files:
    with st.spinner("Calculating Optimised Network..."):
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

        # Adjacency Map for Splits
        adj = defaultdict(list)
        for mid in raw_price_map.keys():
            o, d = mid.split("-")
            adj[o].append(d)

        # 3.2 Optimization Loops (Fixes Splits AND Long-Buys)
        for _ in range(2):
            curr = df.set_index('Match_ID')['New_SDR'].to_dict()
            
            # PART A: Fix Splits
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
            
            # PART B: Fix Long-Buys
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
# --- 3.3 Re‑apply single‑leg pricing AFTER optimisation ---
if slp_enabled:
    final_prices = df.set_index('Match_ID')['New_SDR'].to_dict()

    # First pass: unify fares BEFORE caps
    for mid in list(final_prices.keys()):
        o, d = mid.split("-")
        rev = f"{d}-{o}"

        if rev in final_prices:
            unified = max(final_prices[mid], final_prices[rev])
            unified = round_up(unified, sdr_rounding)

            final_prices[mid] = unified
            final_prices[rev] = unified

    # Second pass: apply caps WITHOUT breaking symmetry
    for mid in list(final_prices.keys()):
        o, d = mid.split("-")
        rev = f"{d}-{o}"

        if rev in final_prices:
            cap_mid = df.loc[df['Match_ID'] == mid, 'Ceiling_Price'].values[0]
            floor_mid = df.loc[df['Match_ID'] == mid, 'Floor_Price'].values[0]

            cap_rev = df.loc[df['Match_ID'] == rev, 'Ceiling_Price'].values[0]
            floor_rev = df.loc[df['Match_ID'] == rev, 'Floor_Price'].values[0]

            # Apply caps to BOTH directions using the strictest limits
            upper = max(cap_mid, cap_rev)
            lower = min(floor_mid, floor_rev)

            final_prices[mid] = min(max(final_prices[mid], lower), upper)
            final_prices[rev] = min(max(final_prices[rev], lower), upper)

    df['New_SDR'] = df['Match_ID'].map(final_prices)

    # UI Calculation
    df['Diff'] = df['New_SDR'] - df['Original_SDR']
    df['Opt_Increase'] = df['New_SDR'] - df['Base_Price']
    df['Status'] = df['Diff'].apply(lambda x: "Increased" if x > 0.01 else ("Decreased" if x < -0.01 else "Unchanged"))

    # --- 4. DASHBOARD ---
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
                            gaps.append({"Journey": f"{n_map.get(A, A)} to {n_map.get(C, C)}", "Split At": n_map.get(B, B), "New Fare": thru, "Split Fare": s_sum, "Difference": round(thru - s_sum, 2)})
        if gaps:
            st.dataframe(pd.DataFrame(gaps).sort_values('Difference', ascending=False).head(300), 
                         column_config={"New Fare": st.column_config.NumberColumn(format="£%.2f"), "Split Fare": st.column_config.NumberColumn(format="£%.2f"), "Difference": st.column_config.NumberColumn(format="£%.2f")},
                         use_container_width=True, hide_index=True)
        else:
            st.success("No Split-Ticket Opportunities Found")
        # Count how many split-ticket issues existed before optimisation
        # (same logic as your detection loop, but using Base_Price instead of New_SDR)
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

        st.markdown(
            (
                f"**Split-ticket opportunities solved:** {split_solved}<br>"
                f"**Remaining:** {split_after}"
            ),
            unsafe_allow_html=True
        )
    with r2c2:
        st.subheader("Remaining Long-Buying Opportunities")

        lb_gaps = []

        for path in SEQUENCES.values():
            # Clean station names for ID matching
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
           st.dataframe(
               pd.DataFrame(lb_gaps).sort_values("Difference", ascending=False).head(30),
               column_config={
                   "Price to B": st.column_config.NumberColumn(format="£%.2f"),
                   "Price to C": st.column_config.NumberColumn(format="£%.2f"),
                   "Difference": st.column_config.NumberColumn(format="£%.2f")
               },
               use_container_width=True,
               hide_index=True
           )
        else:
            st.info("No Long-Buying Opportunities Found")
            # Count long-buy issues BEFORE optimisation
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

        st.markdown(
            (
                f"**Long-buying opportunities solved:** {lb_solved}<br>"
                f"**Remaining:** {lb_after}"
            ),
            unsafe_allow_html=True
        )

    st.divider()
    st.subheader("Full Fare Summary")
    st.dataframe(df[['Origin Description', 'Destination Description', 'Original_SDR', 'New_SDR', 'Status']], 
                 column_config={"Original_SDR": st.column_config.NumberColumn("Original", format="£%.2f"), "New_SDR": st.column_config.NumberColumn("New Fare", format="£%.2f")},
                 use_container_width=True, hide_index=True)
    
    st.download_button("Download New Fares", convert_df_to_csv(df), "Final_Quartz_Fares.csv", "text/csv")
