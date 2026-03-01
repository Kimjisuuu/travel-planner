import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# --- 1. 기본 설정 및 세션 초기화 ---
st.set_page_config(page_title="스마트 여행 플래너", page_icon="🌍", layout="wide")
st.title("🌍 스마트 여행 루트 & 실시간 경비 트래커")

# 데이터 저장을 위한 세션 상태 초기화
if 'route_data' not in st.session_state:
    st.session_state.route_data = []
if 'expense_data' not in st.session_state:
    # 요청하신 대로 '일차'를 제거하고 항목과 금액만 남겼습니다.
    st.session_state.expense_data = pd.DataFrame(columns=['경비 항목', '통화', '입력금액', '환산금액(원)'])
if 'search_results' not in st.session_state:
    st.session_state.search_results = []

# --- 2. 도우미 함수 ---
@st.cache_data(ttl=3600) # 1시간마다 환율 갱신
def get_exchange_rate(base_currency):
    if base_currency == "KRW": return 1.0
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
        response = requests.get(url).json()
        return response['rates']['KRW']
    except:
        return None

@st.cache_data
def search_places(query):
    # 한글 검색 지원 및 여러 개의 연관 장소를 반환하도록 수정했습니다.
    geolocator = Nominatim(user_agent="travel_planner_app")
    try:
        locations = geolocator.geocode(query, exactly_one=False, language='ko', limit=5)
        return locations if locations else []
    except:
        return []

# --- 3. 화면 탭 구성 ---
tab1, tab2 = st.tabs(["🗺️ 여행 루트 & 지도", "💰 실시간 환율 경비장"])

# ==========================================
# 탭 1: 여행 루트 및 지도 시각화
# ==========================================
with tab1:
    col_input, col_map = st.columns([1, 2])
    
    with col_input:
        st.subheader("📍 방문지 검색 및 추가")
        
        # 장소 검색 기능
        search_query = st.text_input("장소 검색 (예: 오사카성, 파리 에펠탑)")
        if st.button("🔍 검색하기"):
            if search_query:
                results = search_places(search_query)
                if results:
                    st.session_state.search_results = results
                else:
                    st.warning("검색 결과가 없습니다. 다른 검색어로 시도해보세요.")
                    st.session_state.search_results = []
        
        # 검색 결과가 있으면 선택할 수 있는 드롭다운 표시
        if st.session_state.search_results:
            # 검색된 주소 목록을 옵션으로 만들기
            options = {loc.address: loc for loc in st.session_state.search_results}
            selected_address = st.selectbox("정확한 주소를 선택해주세요:", list(options.keys()))
            
            if st.button("✅ 경로에 추가하기", use_container_width=True):
                selected_loc = options[selected_address]
                # 긴 주소 대신 쉼표 기준 맨 앞의 이름만 추출
                short_name = selected_address.split(',')[0]
                
                st.session_state.route_data.append({
                    "장소": short_name, 
                    "전체주소": selected_address,
                    "lat": selected_loc.latitude, 
                    "lon": selected_loc.longitude
                })
                # 추가 후 검색 목록 초기화 및 새로고침
                st.session_state.search_results = [] 
                st.rerun()

        # 입력된 루트 목록 및 거리 계산
        if st.session_state.route_data:
            st.markdown("### 📋 현재 루트")
            route_df = pd.DataFrame(st.session_state.route_data)
            
            distances = [0]
            for i in range(1, len(route_df)):
                coord1 = (route_df.loc[i-1, 'lat'], route_df.loc[i-1, 'lon'])
                coord2 = (route_df.loc[i, 'lat'], route_df.loc[i, 'lon'])
                dist = geodesic(coord1, coord2).km
                distances.append(round(dist, 2))
            
            route_df['이전 장소로부터 거리(km)'] = distances
            st.dataframe(route_df[['장소', '이전 장소로부터 거리(km)']], hide_index=True)
            
            if st.button("루트 전체 초기화"):
                st.session_state.route_data = []
                st.rerun()

    with col_map:
        st.subheader("🗺️ 생성된 지도 루트")
        if st.session_state.route_data:
            start_lat = st.session_state.route_data[0]['lat']
            start_lon = st.session_state.route_data[0]['lon']
            m = folium.Map(location=[start_lat, start_lon], zoom_start=13)
            
            coordinates = []
            for idx, row in enumerate(st.session_state.route_data):
                coord = [row['lat'], row['lon']]
                coordinates.append(coord)
                
                html = f"""<div style="font-family: sans-serif; color: white; background-color: #E74C3C; 
                           border-radius: 50%; width: 24px; height: 24px; display: flex; 
                           justify-content: center; align-items: center; font-weight: bold; 
                           border: 2px solid white; box-shadow: 0 0 3px rgba(0,0,0,0.5);">{idx+1}</div>"""
                icon = folium.DivIcon(html=html)
                
                folium.Marker(
                    location=coord,
                    popup=row['장소'],
                    icon=icon
                ).add_to(m)
            
            if len(coordinates) > 1:
                folium.PolyLine(locations=coordinates, color='blue', weight=4, opacity=0.7).add_to(m)
            
            st_folium(m, width=700, height=500)
        else:
            st.info("왼쪽에서 장소를 검색하고 추가하면 지도가 여기에 나타납니다.")

# ==========================================
# 탭 2: 실시간 환율 적용 경비장
# ==========================================
with tab2:
    col_exp_in, col_exp_out = st.columns([1, 2])
    
    with col_exp_in:
        st.subheader("💸 비용 입력")
        # 일차 입력을 없애고 항목과 금액만 받습니다.
        e_memo = st.text_input("경비 항목 (예: 왕복 항공권, 점심식사)")
        e_curr = st.selectbox("통화 선택", ["KRW", "USD", "EUR", "JPY", "GBP", "VND"])
        e_amount = st.number_input("금액", min_value=0.0, step=1.0)
        
        if st.button("경비 추가하기", use_container_width=True):
            if e_memo and e_amount > 0:
                rate = get_exchange_rate(e_curr)
                if rate:
                    converted_krw = e_amount * rate
                    new_expense = pd.DataFrame([{
                        "경비 항목": e_memo,
                        "통화": e_curr,
                        "입력금액": f"{e_amount:,.2f}",
                        "환산금액(원)": int(converted_krw)
                    }])
                    st.session_state.expense_data = pd.concat([st.session_state.expense_data, new_expense], ignore_index=True)
                    st.success("경비가 추가되었습니다!")
                else:
                    st.error("환율 정보를 가져오는데 실패했습니다.")

    with col_exp_out:
        st.subheader("📊 전체 경비 요약")
        
        if not st.session_state.expense_data.empty:
            df = st.session_state.expense_data
            
            # 전체 합산만 깔끔하게 표시
            total_krw = df['환산금액(원)'].sum()
            st.metric(label="총 예상 경비 (현재 환율 자동 적용)", value=f"{total_krw:,.0f} 원")
            
            # 상세 내역 표 (일자별 차트는 제거됨)
            st.markdown("#### 📝 상세 내역")
            st.data_editor(df, use_container_width=True, hide_index=True)
            
            if st.button("경비 내역 초기화"):
                st.session_state.expense_data = pd.DataFrame(columns=['경비 항목', '통화', '입력금액', '환산금액(원)'])
                st.rerun()
        else:
            st.info("지출 내역을 추가하면 오른쪽에 총합계가 자동 계산되어 표시됩니다.")