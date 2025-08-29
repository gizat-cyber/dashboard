#!/usr/bin/env python3
"""
Упрощенный dashboard - только объединенные данные Samsara + Excel
"""

import streamlit as st
import pandas as pd
import requests
import io
import os
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация
SAMSARA_API_TOKEN = os.getenv('SAMSARA_API_TOKEN', '')
SAMSARA_BASE_URL = 'https://api.samsara.com'
EXCEL_URL = 'https://docs.google.com/spreadsheets/d/1QuHCNW8lJ5p6uYx1cvAP70u41l0KIjepxGIgZMr_xeg/export?format=csv&gid=1266601948'

st.set_page_config(
    page_title="🚛 Fleet Dashboard", 
    layout="wide"
)

def get_samsara_stats():
    """Получает статистику ТС из Samsara"""
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
            st.error(f"Ошибка Samsara API: {response.status_code}")
            return []
            
    except Exception as e:
        st.error(f"Ошибка при запросе к Samsara: {e}")
        return []

def get_excel_data():
    """Загружает данные из Excel"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(EXCEL_URL, headers=headers, timeout=10)
        
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text))
            return clean_excel_data(df)
        else:
            st.error(f"Ошибка загрузки Excel: {response.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Ошибка Excel: {e}")
        return pd.DataFrame()

def clean_excel_data(df):
    """Очищает Excel данные"""
    if df.empty:
        return df
    
    # Убираем первый столбец если Unnamed
    if df.columns[0].startswith('Unnamed'):
        df = df.iloc[:, 1:]
    
    # Убираем мусорные записи
    filters_to_remove = ['OLD', 'DKD', 'GNS', 'SOLD']
    first_col = df.columns[0]
    
    for filter_val in filters_to_remove:
        df = df[df[first_col] != filter_val]
    
    # Обрезаем после VIN
    vin_index = None
    for i, col in enumerate(df.columns):
        if 'VIN' in str(col).upper():
            vin_index = i
            break
    
    if vin_index is not None:
        df = df.iloc[:, :vin_index + 1]
    
    return df

def process_combined_data(samsara_data, excel_df):
    """Объединяет данные Samsara и Excel, показывает только совпадения"""
    if not samsara_data or excel_df.empty:
        return pd.DataFrame()
    
    combined_data = []
    
    for vehicle in samsara_data:
        # Данные из Samsara
        vehicle_id = vehicle.get('id', '')
        vehicle_name = vehicle.get('name', '')
        
        # VIN из Samsara
        samsara_vin = vehicle.get('externalIds', {}).get('samsara.vin', '')
        serial = vehicle.get('externalIds', {}).get('samsara.serial', '')
        
        # Пробег из Samsara
        obd_data = vehicle.get('obdOdometerMeters', {})
        obd_miles = round((obd_data.get('value', 0) / 1609.34), 0) if obd_data.get('value') else 0
        obd_time = obd_data.get('time', '') if obd_data else ''
        
        gps_data = vehicle.get('gpsDistanceMeters', {})
        gps_miles = round((gps_data.get('value', 0) / 1609.34), 0) if gps_data.get('value') else 0
        gps_time = gps_data.get('time', '') if gps_data else ''
        
        # Ищем совпадение в Excel по ID или VIN
        excel_match = find_excel_match(vehicle_name, samsara_vin, excel_df)
        
        # Добавляем в список ТОЛЬКО если есть совпадение в Excel
        if excel_match is not None:
            # Извлекаем данные из Excel
            excel_data = extract_excel_data(excel_match, excel_df)
            
            # Рассчитываем дни до проверок
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
    """Ищет совпадение в Excel по ID или VIN"""
    # Сначала ищем по имени ТС (ID)
    for col in excel_df.columns:
        if 'TRUCK' in str(col).upper() or 'ID' in str(col).upper():
            matches = excel_df[excel_df[col].astype(str) == str(vehicle_name)]
            if not matches.empty:
                return matches.index[0]
    
    # Если не найдено, ищем по VIN
    if samsara_vin:
        for col in excel_df.columns:
            if 'VIN' in str(col).upper():
                matches = excel_df[excel_df[col].astype(str) == str(samsara_vin)]
                if not matches.empty:
                    return matches.index[0]
    
    return None

def extract_excel_data(row_index, excel_df):
    """Извлекает данные из строки Excel"""
    row = excel_df.iloc[row_index]
    
    excel_data = {
        'status': '',
        'annual_date': '',
        'pm_date': '',
        'pm_insp_date': ''
    }
    
    # Ищем нужные колонки
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
    """Рассчитывает дни до даты"""
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
    """Определяет статус алерта"""
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

def main():
    st.title("🚛 Fleet Dashboard - Объединенные данные")
    
    # Проверяем токен
    if not SAMSARA_API_TOKEN:
        st.error("❌ Samsara API токен не настроен! Добавьте SAMSARA_API_TOKEN в .env файл")
        return
    
    if st.button("📊 Загрузить данные флота", use_container_width=True):
        with st.spinner("Загружаем и объединяем данные..."):
            # Загружаем данные
            samsara_data = get_samsara_stats()
            excel_df = get_excel_data()
            
            if samsara_data and not excel_df.empty:
                # Объединяем данные
                combined_df = process_combined_data(samsara_data, excel_df)
                
                if not combined_df.empty:
                    st.success(f"✅ Найдено {len(combined_df)} ТС с совпадающими данными")
                    
                    # Основная таблица
                    st.subheader("📋 Флот с проверенными данными")
                    st.dataframe(combined_df, use_container_width=True)
                    
                    # Критические алерты
                    st.subheader("🚨 Критические алерты")
                    
                    # Просроченные
                    overdue_annual = combined_df[combined_df['Annual_Alert'] == 'OVERDUE']
                    overdue_pm = combined_df[combined_df['PM_Alert'] == 'OVERDUE']
                    
                    if not overdue_annual.empty:
                        st.error(f"❌ {len(overdue_annual)} ТС с просроченной Annual проверкой")
                        st.dataframe(overdue_annual[['Vehicle_Name', 'Annual_Date', 'Annual_Days_Remaining']])
                    
                    if not overdue_pm.empty:
                        st.error(f"❌ {len(overdue_pm)} ТС с просроченным PM")
                        st.dataframe(overdue_pm[['Vehicle_Name', 'PM_Date', 'PM_Days_Remaining']])
                    
                    # Критические
                    critical_annual = combined_df[combined_df['Annual_Alert'] == 'CRITICAL']
                    critical_pm = combined_df[combined_df['PM_Alert'] == 'CRITICAL']
                    
                    if not critical_annual.empty:
                        st.warning(f"⚠️ {len(critical_annual)} ТС требуют Annual проверки в течение 30 дней")
                        st.dataframe(critical_annual[['Vehicle_Name', 'Annual_Date', 'Annual_Days_Remaining']])
                    
                    if not critical_pm.empty:
                        st.warning(f"⚠️ {len(critical_pm)} ТС требуют PM в течение 30 дней")
                        st.dataframe(critical_pm[['Vehicle_Name', 'PM_Date', 'PM_Days_Remaining']])
                    
                    # Статистика
                    st.subheader("📊 Статистика")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Всего ТС", len(combined_df))
                    
                    with col2:
                        annual_ok = len(combined_df[combined_df['Annual_Alert'] == 'OK'])
                        st.metric("Annual OK", annual_ok)
                    
                    with col3:
                        pm_ok = len(combined_df[combined_df['PM_Alert'] == 'OK'])
                        st.metric("PM OK", pm_ok)
                    
                    with col4:
                        avg_miles = combined_df['OBD_Odometer_Miles'].mean()
                        st.metric("Средний пробег", f"{avg_miles:,.0f} миль")
                    
                    # Сохраняем
                    combined_df.to_csv('fleet_dashboard_data.csv', index=False)
                    st.info("💾 Данные сохранены в 'fleet_dashboard_data.csv'")
                    
                else:
                    st.warning("⚠️ Не найдено совпадений между Samsara и Excel данными")
            else:
                st.error("❌ Не удалось загрузить данные")

if __name__ == "__main__":
    main()
