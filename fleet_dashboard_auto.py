#!/usr/bin/env python3
"""
Fleet Management Dashboard - Auto-loading version with English Interface
Combined Samsara + Excel Data with Comprehensive Visualizations
"""

import streamlit as st
import pandas as pd
import requests
import io
import os
from datetime import datetime
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# Load environment variables
load_dotenv()

# Configuration
SAMSARA_API_TOKEN = os.getenv('SAMSARA_API_TOKEN', '')
SAMSARA_BASE_URL = 'https://api.samsara.com'
EXCEL_URL = 'https://docs.google.com/spreadsheets/d/1QuHCNW8lJ5p6uYx1cvAP70u41l0KIjepxGIgZMr_xeg/export?format=csv&gid=1266601948'

st.set_page_config(
    page_title="🚛 Fleet Management Dashboard", 
    layout="wide",
    initial_sidebar_state="expanded"
)

def get_samsara_stats():
    """Fetches vehicle statistics from Samsara API"""
    try:
        url = f"{SAMSARA_BASE_URL}/fleet/vehicles/stats"
        headers = {
            'Authorization': f'Bearer {SAMSARA_API_TOKEN}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        params = {
            'types': 'obdOdometerMeters,gpsDistanceMeters',
            'limit': 100
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        else:
            st.error(f"Samsara API Error: {response.status_code}")
            return []
            
    except Exception as e:
        st.error(f"Error fetching Samsara data: {e}")
        return []

def get_excel_data():
    """Loads data from Excel spreadsheet"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(EXCEL_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            return clean_excel_data(df)
        else:
            st.error(f"Excel loading error: {response.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Excel error: {e}")
        return pd.DataFrame()

def clean_excel_data(df):
    """Cleans Excel data by removing unwanted entries"""
    if df.empty:
        return df
    
    # Remove first column if Unnamed
    if df.columns[0].startswith('Unnamed'):
        df = df.iloc[:, 1:]
    
    # Remove junk entries
    filters_to_remove = ['OLD', 'DKD', 'GNS', 'SOLD']
    first_col = df.columns[0]
    
    for filter_val in filters_to_remove:
        df = df[df[first_col] != filter_val]
    
    # Trim columns after VIN
    vin_index = None
    for i, col in enumerate(df.columns):
        if 'VIN' in str(col).upper():
            vin_index = i
            break
    
    if vin_index is not None:
        df = df.iloc[:, :vin_index + 1]
    
    return df

def process_combined_data(samsara_data, excel_df):
    """Combines Samsara and Excel data, shows only matches"""
    if not samsara_data or excel_df.empty:
        return pd.DataFrame()
    
    combined_data = []
    
    for vehicle in samsara_data:
        # Samsara data
        vehicle_id = vehicle.get('id', '')
        vehicle_name = vehicle.get('name', '')
        
        # VIN from Samsara
        samsara_vin = vehicle.get('externalIds', {}).get('samsara.vin', '')
        serial = vehicle.get('externalIds', {}).get('samsara.serial', '')
        
        # Mileage from Samsara
        obd_data = vehicle.get('obdOdometerMeters', {})
        obd_miles = round((obd_data.get('value', 0) / 1609.34), 0) if obd_data.get('value') else 0
        obd_time = obd_data.get('time', '') if obd_data else ''
        
        gps_data = vehicle.get('gpsDistanceMeters', {})
        gps_miles = round((gps_data.get('value', 0) / 1609.34), 0) if gps_data.get('value') else 0
        gps_time = gps_data.get('time', '') if gps_data else ''
        
        # Find match in Excel by ID or VIN
        excel_match = find_excel_match(vehicle_name, samsara_vin, excel_df)
        
        # Add to list ONLY if there's a match in Excel
        if excel_match is not None:
            # Extract data from Excel
            excel_data = extract_excel_data(excel_match, excel_df)
            
            # Calculate days until inspections
            annual_days = calculate_days_remaining(excel_data.get('annual_date'))
            pm_days = calculate_days_remaining(excel_data.get('pm_date'))
            pm_insp_days = calculate_days_remaining(excel_data.get('pm_insp_date'))
            
            combined_info = {
                'Vehicle_ID': vehicle_id,
                'Vehicle_Name': vehicle_name,
                'VIN': samsara_vin,
                'Serial': serial,
                'OBD_Odometer_Miles': int(obd_miles),
                'GPS_Distance_Miles': int(gps_miles),
                'OBD_Last_Update': obd_time,
                'GPS_Last_Update': gps_time,
                'Status': excel_data.get('status', ''),
                'Annual_Date': excel_data.get('annual_date', ''),
                'Annual_Days_Remaining': annual_days,
                'PM_Date': excel_data.get('pm_date', ''),
                'PM_Days_Remaining': pm_days,
                'PM_Insp_Date': excel_data.get('pm_insp_date', ''),
                'PM_Insp_Days_Remaining': pm_insp_days,
                'Annual_Alert': get_alert_status(annual_days),
                'PM_Alert': get_alert_status(pm_days),
                'PM_Insp_Alert': get_alert_status(pm_insp_days)
            }
            combined_data.append(combined_info)
    
    return pd.DataFrame(combined_data)

def find_excel_match(vehicle_name, samsara_vin, excel_df):
    """Finds match in Excel by ID or VIN"""
    # First search by vehicle name (ID)
    for col in excel_df.columns:
        if 'TRUCK' in str(col).upper() or 'ID' in str(col).upper():
            matches = excel_df[excel_df[col].astype(str) == str(vehicle_name)]
            if not matches.empty:
                return matches.index[0]
    
    # If not found, search by VIN
    if samsara_vin:
        for col in excel_df.columns:
            if 'VIN' in str(col).upper():
                matches = excel_df[excel_df[col].astype(str) == str(samsara_vin)]
                if not matches.empty:
                    return matches.index[0]
    
    return None

def extract_excel_data(row_index, excel_df):
    """Extracts data from Excel row"""
    row = excel_df.iloc[row_index]
    
    excel_data = {
        'status': '',
        'annual_date': '',
        'pm_date': '',
        'pm_insp_date': ''
    }
    
    # Find relevant columns
    for col in excel_df.columns:
        col_upper = str(col).upper()
        
        if 'STATUS' in col_upper:
            excel_data['status'] = str(row[col]) if pd.notna(row[col]) else ''
        elif 'ANNUAL' in col_upper:
            excel_data['annual_date'] = str(row[col]) if pd.notna(row[col]) else ''
        elif 'PM' in col_upper and 'DATE' in col_upper:
            excel_data['pm_date'] = str(row[col]) if pd.notna(row[col]) else ''
        elif 'PM' in col_upper and 'INSP' in col_upper:
            excel_data['pm_insp_date'] = str(row[col]) if pd.notna(row[col]) else ''
    
    return excel_data

def calculate_days_remaining(date_value):
    """Calculates days until date"""
    if not date_value or date_value == '' or pd.isna(date_value):
        return None
    
    try:
        date_formats = ['%m/%d/%Y', '%Y-%m-%d', '%d.%m.%Y', '%m-%d-%Y']
        
        for fmt in date_formats:
            try:
                target_date = datetime.strptime(str(date_value), fmt)
                today = datetime.now()
                return (target_date - today).days
            except ValueError:
                continue
        
        return None
    except:
        return None

def get_alert_status(days_remaining):
    """Determines alert status"""
    if days_remaining is None:
        return "No Data"
    elif days_remaining < 0:
        return "OVERDUE"
    elif days_remaining <= 30:
        return "CRITICAL"
    elif days_remaining <= 60:
        return "WARNING"
    else:
        return "OK"

def create_simple_overview_chart(df):
    """Creates a simple overview chart for faster loading"""
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=['Compliance Status', 'Fleet Health Metrics'],
        specs=[[{'type':'domain'}, {'type':'xy'}]]
    )
    
    # 1. Compliance pie chart
    compliance_counts = []
    for _, row in df.iterrows():
        if row['Annual_Alert'] == 'OK' and row['PM_Alert'] == 'OK':
            compliance_counts.append('Fully Compliant')
        elif row['Annual_Alert'] in ['OVERDUE', 'CRITICAL'] or row['PM_Alert'] in ['OVERDUE', 'CRITICAL']:
            compliance_counts.append('Needs Attention')
        else:
            compliance_counts.append('Warning Status')
    
    compliance_series = pd.Series(compliance_counts).value_counts()
    colors = {'Fully Compliant': '#27ae60', 'Warning Status': '#f39c12', 'Needs Attention': '#e74c3c'}
    
    fig.add_trace(go.Pie(
        labels=compliance_series.index,
        values=compliance_series.values,
        marker_colors=[colors.get(x, '#95a5a6') for x in compliance_series.index],
        hole=0.4,
        textinfo='label+percent+value'
    ), 1, 1)
    
    # 2. Mileage vs Alert Status
    alert_categories = ['OK', 'WARNING', 'CRITICAL', 'OVERDUE']
    mileage_by_alert = []
    
    for alert in alert_categories:
        alert_data = df[df['Annual_Alert'] == alert]
        if not alert_data.empty:
            avg_mileage = alert_data['OBD_Odometer_Miles'].mean()
            mileage_by_alert.append(avg_mileage)
        else:
            mileage_by_alert.append(0)
    
    fig.add_trace(go.Bar(
        x=alert_categories,
        y=mileage_by_alert,
        marker_color=['#27ae60', '#f39c12', '#e74c3c', '#8e44ad'],
        text=[f'{miles:,.0f}' for miles in mileage_by_alert],
        textposition='auto'
    ), 1, 2)
    
    fig.update_layout(
        title_text="🎯 Fleet Overview Dashboard",
        title_x=0.5,
        height=400,
        showlegend=False
    )
    
    fig.update_xaxes(title_text="Alert Status", row=1, col=2)
    fig.update_yaxes(title_text="Average Mileage", row=1, col=2)
    
    return fig

def create_metrics_summary(df):
    """Creates summary metrics for the fleet"""
    total_vehicles = len(df)
    
    # Compliance metrics
    annual_ok = len(df[df['Annual_Alert'] == 'OK'])
    annual_overdue = len(df[df['Annual_Alert'] == 'OVERDUE'])
    annual_critical = len(df[df['Annual_Alert'] == 'CRITICAL'])
    
    pm_ok = len(df[df['PM_Alert'] == 'OK'])
    pm_overdue = len(df[df['PM_Alert'] == 'OVERDUE'])
    pm_critical = len(df[df['PM_Alert'] == 'CRITICAL'])
    
    # Mileage metrics
    avg_mileage = df['OBD_Odometer_Miles'].mean()
    max_mileage = df['OBD_Odometer_Miles'].max()
    high_mileage_count = len(df[df['OBD_Odometer_Miles'] > 400000])
    
    # Fleet health score
    fully_compliant = len(df[(df['Annual_Alert'] == 'OK') & (df['PM_Alert'] == 'OK')])
    fleet_health = (fully_compliant / total_vehicles) * 100 if total_vehicles > 0 else 0
    
    return {
        'total_vehicles': total_vehicles,
        'annual_ok': annual_ok,
        'annual_overdue': annual_overdue,
        'annual_critical': annual_critical,
        'pm_ok': pm_ok,
        'pm_overdue': pm_overdue,
        'pm_critical': pm_critical,
        'avg_mileage': avg_mileage,
        'max_mileage': max_mileage,
        'high_mileage_count': high_mileage_count,
        'fleet_health': fleet_health
    }

def main():
    st.title("🚛 Fleet Management Dashboard - Auto-Loading")
    
    # Sidebar with configuration
    st.sidebar.header("🔧 Configuration")
    
    # Check API token
    global SAMSARA_API_TOKEN
    
    if not SAMSARA_API_TOKEN:
        st.sidebar.error("❌ Samsara API token not configured!")
        st.sidebar.info("Add SAMSARA_API_TOKEN to .env file")
        
        # Allow manual token input for demo
        manual_token = st.sidebar.text_input("Enter Samsara API Token:", type="password")
        if manual_token:
            SAMSARA_API_TOKEN = manual_token
            st.sidebar.success("✅ Token set for this session")
    else:
        st.sidebar.success("✅ API Configuration Ready")
    
    # Dashboard settings
    st.sidebar.subheader("📊 Dashboard Settings")
    auto_refresh = st.sidebar.checkbox("Auto-refresh data", value=False)
    refresh_interval = st.sidebar.selectbox("Refresh interval (seconds):", [30, 60, 300, 900], index=1)
    
    # Initialize session state for data caching
    if 'fleet_data_loaded' not in st.session_state:
        st.session_state.fleet_data_loaded = False
        st.session_state.combined_df = None
        st.session_state.metrics = None
        st.session_state.last_update = None
    
    # Auto-refresh logic
    if auto_refresh and st.session_state.last_update:
        time_since_update = (datetime.now() - st.session_state.last_update).total_seconds()
        if time_since_update > refresh_interval:
            st.session_state.fleet_data_loaded = False
    
    # Manual refresh button
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.session_state.fleet_data_loaded:
            st.success("✅ Fleet data loaded and ready")
        else:
            st.info("🔄 Loading fleet data...")
    with col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.session_state.fleet_data_loaded = False
            st.session_state.combined_df = None
            st.session_state.metrics = None
            st.rerun()
    
    # Load data automatically or use cached data
    if not st.session_state.fleet_data_loaded:
        with st.spinner("🔄 Fetching data from Samsara and Excel..."):
            # Load data from sources
            samsara_data = get_samsara_stats()
            excel_df = get_excel_data()
            
            if samsara_data and not excel_df.empty:
                # Combine and process data
                combined_df = process_combined_data(samsara_data, excel_df)
                
                if not combined_df.empty:
                    # Cache the data in session state
                    st.session_state.combined_df = combined_df
                    st.session_state.metrics = create_metrics_summary(combined_df)
                    st.session_state.fleet_data_loaded = True
                    st.session_state.last_update = datetime.now()
                    
                    st.success(f"✅ Successfully loaded {len(combined_df)} vehicles with complete data")
                else:
                    st.warning("⚠️ No matching vehicles found between Samsara and Excel data")
                    st.info("Please check that vehicle IDs or VINs match between both systems")
                    return
            else:
                st.error("❌ Failed to load data from one or more sources")
                if not samsara_data:
                    st.error("- Samsara API connection failed")
                if excel_df.empty:
                    st.error("- Excel data loading failed")
                return
    
    # Use cached data if available
    if st.session_state.fleet_data_loaded and st.session_state.combined_df is not None:
        combined_df = st.session_state.combined_df
        metrics = st.session_state.metrics
        
        # Display key metrics
        st.header("📊 Fleet Overview")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("🚛 Total Fleet", metrics['total_vehicles'])
        with col2:
            st.metric("💚 Fleet Health", f"{metrics['fleet_health']:.1f}%",
                    delta=f"{metrics['fleet_health'] - 85:.1f}%" if metrics['fleet_health'] >= 85 else f"{metrics['fleet_health'] - 85:.1f}%")
        with col3:
            st.metric("📅 Annual Compliant", f"{metrics['annual_ok']}/{metrics['total_vehicles']}",
                    delta=f"-{metrics['annual_overdue']} overdue")
        with col4:
            st.metric("🔧 PM Compliant", f"{metrics['pm_ok']}/{metrics['total_vehicles']}",
                    delta=f"-{metrics['pm_overdue']} overdue")
        with col5:
            st.metric("📈 Avg Mileage", f"{metrics['avg_mileage']:,.0f} mi",
                    delta=f"Max: {metrics['max_mileage']:,.0f}")
        
        # Quick overview chart
        st.plotly_chart(create_simple_overview_chart(combined_df), use_container_width=True)
        
        # Create simplified tabs
        tab1, tab2 = st.tabs(["🚨 Critical Alerts", "📋 Fleet Data"])
        
        with tab1:
            st.header("🚨 Vehicles Requiring Immediate Attention")
            
            # Critical vehicles
            critical_vehicles = combined_df[
                (combined_df['Annual_Alert'].isin(['OVERDUE', 'CRITICAL'])) |
                (combined_df['PM_Alert'].isin(['OVERDUE', 'CRITICAL']))
            ]
            
            if not critical_vehicles.empty:
                st.error(f"⚠️ {len(critical_vehicles)} vehicles require immediate attention")
                
                # Group by priority
                overdue = critical_vehicles[
                    (critical_vehicles['Annual_Alert'] == 'OVERDUE') |
                    (critical_vehicles['PM_Alert'] == 'OVERDUE')
                ]
                
                critical = critical_vehicles[
                    (critical_vehicles['Annual_Alert'] == 'CRITICAL') |
                    (critical_vehicles['PM_Alert'] == 'CRITICAL')
                ]
                
                if not overdue.empty:
                    st.subheader("🔴 OVERDUE Maintenance")
                    st.dataframe(
                        overdue[['Vehicle_Name', 'OBD_Odometer_Miles', 'Annual_Alert', 'PM_Alert', 'Annual_Days_Remaining', 'PM_Days_Remaining']],
                        use_container_width=True
                    )
                
                if not critical.empty:
                    st.subheader("🟡 CRITICAL (Due Soon)")
                    st.dataframe(
                        critical[['Vehicle_Name', 'OBD_Odometer_Miles', 'Annual_Alert', 'PM_Alert', 'Annual_Days_Remaining', 'PM_Days_Remaining']],
                        use_container_width=True
                    )
            else:
                st.success("✅ No vehicles require immediate attention!")
            
            # High mileage vehicles
            high_mileage = combined_df[combined_df['OBD_Odometer_Miles'] > 400000]
            if not high_mileage.empty:
                st.subheader(f"📊 High Mileage Vehicles ({len(high_mileage)} vehicles >400K miles)")
                st.dataframe(
                    high_mileage[['Vehicle_Name', 'OBD_Odometer_Miles', 'Annual_Alert', 'PM_Alert']].sort_values('OBD_Odometer_Miles', ascending=False),
                    use_container_width=True
                )
        
        with tab2:
            st.header("📋 Complete Fleet Data")
            
            # Filters
            col1, col2, col3 = st.columns(3)
            
            with col1:
                annual_filter = st.selectbox("Annual Status:", 
                                           ['All'] + list(combined_df['Annual_Alert'].unique()))
            with col2:
                pm_filter = st.selectbox("PM Status:", 
                                        ['All'] + list(combined_df['PM_Alert'].unique()))
            with col3:
                vehicle_search = st.text_input("Search Vehicles:", placeholder="Enter vehicle number")
            
            # Apply filters
            filtered_df = combined_df.copy()
            
            if annual_filter != 'All':
                filtered_df = filtered_df[filtered_df['Annual_Alert'] == annual_filter]
            if pm_filter != 'All':
                filtered_df = filtered_df[filtered_df['PM_Alert'] == pm_filter]
            if vehicle_search:
                filtered_df = filtered_df[filtered_df['Vehicle_Name'].str.contains(vehicle_search, case=False, na=False)]
            
            st.info(f"Showing {len(filtered_df)} of {len(combined_df)} vehicles")
            
            # Display filtered data
            st.dataframe(filtered_df, use_container_width=True, height=500)
            
            # Export button
            if st.button("📊 Export to CSV", use_container_width=True):
                csv_file = filtered_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_file,
                    file_name=f"fleet_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # Last update info
        if st.session_state.last_update:
            st.sidebar.info(f"Last updated: {st.session_state.last_update.strftime('%H:%M:%S')}")
        
        # Auto-refresh countdown
        if auto_refresh:
            placeholder = st.sidebar.empty()
            import time
            time_remaining = refresh_interval
            if st.session_state.last_update:
                time_elapsed = (datetime.now() - st.session_state.last_update).total_seconds()
                time_remaining = max(0, refresh_interval - time_elapsed)
            
            placeholder.info(f"Next refresh in: {time_remaining:.0f}s")

if __name__ == "__main__":
    main()
