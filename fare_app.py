import streamlit as st
import pandas as pd
import math
import os
from collections import defaultdict
import plotly.graph_objects as go

st.set_page_config(page_title="Anomaly Adjuster", layout="wide")

# --- CACHE THE CSV CONVERSION --
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
    "Alton Main Line": ["ALTON", "BENTLEY", "FARNHAM", "ALDERSHOT", "ASH VALE", "BROOKWOOD", "WOKING", "WEST BYFLEET", "BYFLEET & NEW HAW", "WEYBRIDGE", "WALTON-ON-THAMES", "HERSHAM", "ESHER", "SURBITON", "CLAPHAM JUNCTION LONDON", "QUEENSTOWN ROAD(BATTERSEA)", "LONDON BR", "ZONE R1256 LONDON"]
}

# --- 2. SIDEBAR FILE UPLOADS ---
st.sidebar.header("Data Upload Center")
uploaded_main = st.sidebar.file_uploader("Upload Main Sheet (Excel)", type=["xlsx"])
uploaded_jr = st.sidebar.file_uploader("Upload Journeys & Revenue (Excel)", type=["xlsx"])

if uploaded_main is not None and uploaded_jr is not None:
    # Load DataFrames
    df_main = pd.read_excel(uploaded_main)
    df_jr = pd.read_excel(uploaded_jr)
    
    # --- 3. DYNAMIC INPUT SELECTORS IN SIDEBAR ---
    st.sidebar.markdown("---")
    st.sidebar.header("Model Controls")
    
    ticket_options = ["SDS", "CDS", "SDR", "CDR", "7DS"]
    chosen_ticket = st.sidebar.selectbox("Select Target Fare Product:", ticket_options, index=2) # Default SDR
    
    # Helper definitions for products
    alt_product = "CDR" if chosen_ticket == "SDR" else "CDS" if chosen_ticket == "SDS" else chosen_ticket
    
    # Extract unique stations dynamically from main data
    all_stations = sorted(list(set(df_main['Origin Description'].dropna().astype(str).tolist() + df_main['Destination Description'].dropna().astype(str).tolist())))
    
    start_stn = st.sidebar.selectbox("Select Line Origin Station:", all_stations, index=all_stations.index("ALTON") if "ALTON" in all_stations else 0)
    end_stn = st.sidebar.selectbox("Select Line Destination Milestone:", all_stations, index=all_stations.index("LONDON BR") if "LONDON BR" in all_stations else 0)
    
    # --- 4. DATA PRE-PROCESSING & MERGING ---
    df_main['Match_ID'] = df_main['Origin Code'].astype(str) + "-" + df_main['Destination Code'].astype(str)
    df_jr['Match_ID'] = df_jr['True Origin Code'].astype(str) + "-" + df_jr['True Destination Code'].astype(str)
    
    # Isolate relevant rows matching product constraints
    df_jr_filtered = df_jr[df_jr['Product Code'] == chosen_ticket].copy()
    
    # Group and aggregate volume / revenue
    jr_agg = df_jr_filtered.groupby('Match_ID').agg({
        'JOURNEYS': 'sum',
        'REVENUE': 'sum'
    }).reset_index().rename(columns={'JOURNEYS': 'Filtered_Journeys', 'REVENUE': 'Old_Ticket_Revenue'})
    
    # Build complete merged framework
    df = pd.merge(df_main, jr_agg, on='Match_ID', how='left')
    df['Filtered_Journeys'] = df['Filtered_Journeys'].fillna(0)
    df['Old_Ticket_Revenue'] = df['Old_Ticket_Revenue'].fillna(0)
    
    # Set standard dynamic column aliases safely
    df['Display_Original_Fare'] = df[chosen_ticket]
    
    # --- SIMULATE MODEL CALCULATIONS ---
    df['New_SDR'] = df['SDR'] # Placeholder math block logic
    df['Original_SDR'] = df['SDR']
    df['Original_SDS'] = df.get('SDS', df['Display_Original_Fare'])
    df['Original_CDS'] = df.get('CDS', df['Display_Original_Fare'])
    df['Original_SDR'] = df.get('SDR', df['Display_Original_Fare'])
    df['Original_CDR'] = df.get('CDR', df['Display_Original_Fare'])
    df['Original_7DS'] = df.get('7DS', df['Display_Original_Fare'])
    df['Old_Super_OffPeak'] = df.get('SUA', df['Display_Original_Fare'] * 0.8)
    
    # Optimization dynamic target mapping dummy values
    df['Display_New_Fare'] = df['Display_Original_Fare'] * 1.03 # 3% increase demo placeholder
    df['Opt_Increase'] = (df['Display_New_Fare'] - df['Display_Original_Fare']).apply(lambda x: x if x > 0 else 0.0)
    df['Diff'] = df['Display_New_Fare'] - df['Display_Original_Fare']
    df['Predicted_Journeys'] = df['Filtered_Journeys'] * 0.98
    df['New_Ticket_Revenue'] = df['Predicted_Journeys'] * df['Display_New_Fare']
    df['Revenue_Impact'] = df['New_Ticket_Revenue'] - df['Old_Ticket_Revenue']
    df['Abs_Revenue_Impact'] = df['Revenue_Impact'].abs()
    df['Status'] = "Optimised"
    
    # Build dummy split checking structure
    adj = defaultdict(list)
    for _, r in df.iterrows():
        adj[str(r['Origin Code'])].append(str(r['Destination Code']))
        
    f_prices_new = df.set_index('Match_ID')['Display_New_Fare'].to_dict()
    direct_fare_new = f_prices_new.get(f"{start_stn}-{end_stn}", 45.0)
    
    chart_data_splits = [] # Populate with explicit segment milestones
    
    # --- 5. IDENTIFY PASSING SEQUENCE ---
    start_clean = start_stn.replace(" ", "")
    end_clean = end_stn.replace(" ", "")
    active_route = None
    
    for route_name, sequence in SEQUENCES.items():
        clean_seq = [s.replace(" ", "") for s in sequence]
        if start_clean in clean_seq and end_clean in clean_seq:
            idx_start = clean_seq.index(start_clean)
            idx_end = clean_seq.index(end_clean)
            if idx_start < idx_end:
                active_route = sequence[idx_start:idx_end+1]
                break

    if active_route:
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
                    "Old Fare (£)": today_f if today_f > 0 else None,
                    "New Fare (£)": new_f,
                    "Old Super Off-Peak (£)": sop_f if sop_f > 0 else None,
                    "Change (£)": round(new_f - today_f, 2) if today_f > 0 else None
                })

        # =========================================================================
        # ✨ INITIALIZE TABS RIGHT HERE
        # =========================================================================
        tab1, tab2 = st.tabs(["📊 Hub Analytics", "🔍 Market Opportunities"])

        # --- TAB 1 CONTENT ---
        with tab1:
            gc1, gc2 = st.columns(2)
            
            with gc1:
                if chart_data_splits and direct_fare_new > 0:
                    df_splits = pd.DataFrame(chart_data_splits)
                    fig_splits = go.Figure()
                    
                    fig_splits.add_trace(go.Bar(
                        x=df_splits["Intermediate Station"], y=df_splits["Pure Split"],
                        name=f"Pure Split ({chosen_ticket} + {chosen_ticket})", 
                        marker_color='rgb(55, 83, 109)',
                        customdata=df_splits[["Pure L1", "Pure L2"]],
                        hovertemplate="<b>Split Station: %{x}</b><br>Total Split Cost: £%{y:.2f}<br>Leg 1 ("+chosen_ticket+"): £%{customdata[0]:.2f}<br>Leg 2 ("+chosen_ticket+"): £%{customdata[1]:.2f}<extra></extra>"
                    ))
                    
                    if chosen_ticket != "7DS" and chosen_ticket != alt_product:
                        fig_splits.add_trace(go.Bar(
                            x=df_splits["Intermediate Station"], y=df_splits["Mix A"],
                            name=f"Mixed Combo A ({chosen_ticket} + {alt_product})", 
                            marker_color='rgb(26, 118, 141)',
                            customdata=df_splits[["Mix A L1", "Mix A L2"]],
                            hovertemplate="<b>Split Station: %{x}</b><br>Total Split Cost: £%{y:.2f}<br>Leg 1 ("+chosen_ticket+"): £%{customdata[0]:.2f}<br>Leg 2 ("+alt_product+"): £%{customdata[1]:.2f}<extra></extra>"
                        ))
                        
                        fig_splits.add_trace(go.Bar(
                            x=df_splits["Intermediate Station"], y=df_splits["Mix B"],
                            name=f"Mixed Combo B ({alt_product} + {chosen_ticket})", 
                            marker_color='rgb(158, 201, 225)',
                            customdata=df_splits[["Mix B L1", "Mix B L2"]],
                            hovertemplate="<b>Split Station: %{x}</b><br>Total Split Cost: £%{y:.2f}<br>Leg 1 ("+alt_product+"): £%{customdata[1]:.2f}<br>Leg 2 ("+chosen_ticket+"): £%{customdata[1]:.2f}<extra></extra>"
                        ))
                    
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
                    
                    df_comp["Variance_Text"] = df_comp["Change (£)"].apply(
                        lambda x: f"+£{x:.2f}" if x > 0 else f"-£{abs(x):.2f}" if x < 0 else "£0.00" if pd.notna(x) else ""
                    )
                    
                    fig_comp = go.Figure()
                    
                    if df_comp["Old Fare (£)"].notna().any():
                        fig_comp.add_trace(go.Scatter(
                            x=df_comp["Station"], y=df_comp["Old Fare (£)"], mode="lines+markers",
                            name="Fares Today", line=dict(color="#1f77b4", width=3), marker=dict(size=8),
                            connectgaps=True,
                            hovertemplate="<b>To: %{x}</b><br>Fares Today: £%{y:.2f}<extra></extra>"
                        ))
                    
                    if chosen_ticket in ["CDR", "CDS"] and df_comp["Old Super Off-Peak (£)"].notna().any():
                        fig_comp.add_trace(go.Scatter(
                            x=df_comp["Station"], y=df_comp["Old Super Off-Peak (£)"], mode="lines+markers",
                            name="Old Super Off-Peak (Withdrawn)", line=dict(color="orange", width=2, dash="dot"), marker=dict(size=6),
                            hovertemplate="<b>To: %{x}</b><br>Withdrawn SOP Fare: £%{y:.2f}<extra></extra>"
                        ))
                    
                    fig_comp.add_trace(go.Scatter(
                        x=df_comp["Station"], y=df_comp["New Fare (£)"], mode="lines+markers",
                        name=f"New Optimized {chosen_ticket}", line=dict(color="#d62728", width=3), marker=dict(size=8),
                        customdata=df_comp["Variance_Text"],
                        hovertemplate="<b>To: %{x}</b><br>New Fare: £%{y:.2f}<br>True Variance: %{customdata}<extra></extra>" if df_comp["Change (£)"].notna().any() else "<b>To: %{x}</b><br>New Fare: £%{y:.2f}<extra></extra>"
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

        # --- TAB 2 CONTENT ---
        with tab2:
            r2c1, r2c2 = st.columns(2)
            with r2c1:
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

        # =========================================================================
        # 🌍 GLOBAL AREA (OUTSIDE TABS - AT THE BOTTOM)
        # =========================================================================
        st.divider()
        r1c1, r1c2 = st.columns(2)
        with r1c1:
            st.subheader(f"Top 10 Price Increases ({chosen_ticket})")
            st.dataframe(df.sort_values('Opt_Increase', ascending=False).head(10)[['Origin Description', 'Destination Description', 'Display_Original_Fare', 'Display_New_Fare', 'Opt_Increase']], 
                         column_config={"Display_Original_Fare": st.column_config.NumberColumn("Baseline", format="£%.2f"), "Display_New_Fare": st.column_config.NumberColumn("New Fare", format="£%.2f"), "Opt_Increase": st.column_config.NumberColumn("Increase", format="£%.2f")}, 
                         use_container_width=True, hide_index=True)
        with r1c2:
            st.subheader(f"Top 10 Price Decreases ({chosen_ticket})")
            dec_disp = df.sort_values('Diff', ascending=True).head(10).copy()
            dec_disp['Diff'] = dec_disp['Diff'].abs()
            st.dataframe(dec_disp[['Origin Description', 'Destination Description', 'Display_Original_Fare', 'Display_New_Fare', 'Diff']], 
                         column_config={"Display_Original_Fare": st.column_config.NumberColumn("Original", format="£%.2f"), "Display_New_Fare": st.column_config.NumberColumn("New Fare", format="£%.2f"), "Diff": st.column_config.NumberColumn("Decrease", format="-£%.2f")}, 
                         use_container_width=True, hide_index=True)

        # --- ROW 3: JOURNEY & REVENUE IMPACT TABLES ---
        st.divider()
        r3c1, r3c2 = st.columns(2)
        with r3c1:
            st.subheader("Biggest Journey Volume Changes")
            st.caption(f"Flows with price steps affecting highest volume of **{chosen_ticket}** journeys")
            
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
        st.info(f"No predefined line of route connects **{start_stn.title()}** to **{end_stn.title()}** in that direction.")
else:
    st.info("Please upload fare spreadsheets in the sidebar to populate the dynamic optimization model dashboard.")
