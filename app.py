import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from deep_translator import GoogleTranslator

# --- 1. 기본 설정 및 세션 초기화 ---
st.set_page_config(page_title="스마트 여행 플래너", page_icon="🌍", layout="wide")

# 데이터 저장을 위한 세션 상태 초기화
if 'route_data' not in st.session_state:
    st.session_state.route_data = []
if 'expense_data' not in st.session_state:
    st.session_state.expense_data = pd.DataFrame(columns=['경비 항목', '통화', '입력금액', '환산금액(원)'])
if 'search_results' not in st.session_state:
    st.session_state.search_results = []

# --- 2. 국가 및 도시, 언어 데이터 ---
COUNTRY_DATA = {
    "일본": {"도시": ["도쿄", "오사카", "후쿠오카", "삿포로", "교토"], "언어": "ja"},
    "프랑스": {"도시": ["파리", "마르세유", "니스", "리옹"], "언어": "fr"},
    "미국": {"도시": ["뉴욕", "로스앤젤레스", "라스베이거스", "시카고", "하와이"], "언어": "en"},
    "영국": {"도시": ["런던", "에든버러", "맨체스터"], "언어": "en"},
    "베트남": {"도시": ["다낭", "하노이", "호치민", "나트랑"], "언어": "vi"},
    "태국": {"도시": ["방콕", "푸껫", "치앙마이"], "언어": "th"},
    "대한민국": {"도시": ["서울", "부산", "제주", "인천"], "언어": "ko"},
    "기타(직접 검색)": {"도시": [], "언어": "en"} # 기본 영어 번역
}

# --- 3. 도우미 함수 ---
@st.cache_data(ttl=3600)
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
    geolocator = Nominatim(user_agent="travel_planner_app")
    try:
        locations = geolocator.geocode(query, exactly_one=False, language='ko', limit=5)
        return locations if locations else []
    except:
        return []

@st.cache_data(ttl=1800) # 30분마다 날씨 갱신
def get_weather(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,precipitation&timezone=auto"
        res = requests.get(url).json()
        return res['current']
    except:
        return None

def num_to_kr(num):
    """숫자를 한국어 단위(만, 억)로 변환해주는 함수"""
    if num == 0: return "0"
    num = int(num)
    units = ["", "만 ", "억 ", "조 "]
    result = []
    i = 0
    while num > 0:
        num, r = divmod(num, 10000)
        if r > 0:
            result.append(f"{r:,}{units[i]}")
        i += 1
    return "".join(reversed(result)).strip() + " 원"

# ==========================================
# 상단 패널: 날씨 & 번역
# ==========================================
st.title("🌍 스마트 여행 플래너")

with st.expander("🌤️ 실시간 날씨 & 🗣️ 빠른 번역 (여기를 눌러 여닫으세요)", expanded=True):
    col_w1, col_w2, col_t = st.columns([1, 1, 2])
    
    with col_w1:
        selected_country = st.selectbox("여행 국가 선택", list(COUNTRY_DATA.keys()))
        
    with col_w2:
        if selected_country == "기타(직접 검색)":
            selected_city = st.text_input("도시명 입력 (예: 로마)")
        else:
            selected_city = st.selectbox("주요 도시 선택", COUNTRY_DATA[selected_country]["도시"])
            
    with col_t:
        st.markdown("**🗣️ 빠른 번역기**")
        text_to_translate = st.text_input("한국어로 입력하세요:", placeholder="예: 화장실이 어디에 있나요?")
        target_lang = COUNTRY_DATA[selected_country]["언어"]
        
        if text_to_translate:
            try:
                translated = GoogleTranslator(source='ko', target=target_lang).translate(text_to_translate)
                st.info(f"**번역 결과:** {translated}")
            except:
                st.error("번역 서버에 일시적인 오류가 있습니다.")

    # 날씨 정보 표시
    if selected_city:
        locs = search_places(f"{selected_country} {selected_city}")
        if locs:
            lat, lon = locs[0].latitude, locs[0].longitude
            weather = get_weather(lat, lon)
            if weather:
                w_col1, w_col2, w_col3 = st.columns(3)
                w_col1.metric("🌡️ 현재 기온", f"{weather['temperature_2m']} °C")
                w_col2.metric("🤗 체감 온도", f"{weather['apparent_temperature']} °C")
                w_col3.metric("☔ 강수량 (현재)", f"{weather['precipitation']} mm")
            else:
                st.caption("현재 날씨 정보를 불러올 수 없습니다.")


# ==========================================
# 화면 탭 구성
# ==========================================
tab1, tab2 = st.tabs(["🗺️ 여행 루트 & 지도", "💰 실시간 환율 경비장"])

# --- 탭 1: 여행 루트 --- (기존과 동일)
with tab1:
    col_input, col_map = st.columns([1, 2])
    with col_input:
        st.subheader("📍 방문지 검색 및 추가")
        search_query = st.text_input("장소 검색 (예: 오사카성, 파리 에펠탑)")
        if st.button("🔍 검색하기"):
            if search_query:
                st.session_state.search_results = search_places(search_query)
                if not st.session_state.search_results:
                    st.warning("검색 결과가 없습니다.")
                    
        if st.session_state.search_results:
            options = {loc.address: loc for loc in st.session_state.search_results}
            selected_address = st.selectbox("정확한 주소를 선택해주세요:", list(options.keys()))
            
            if st.button("✅ 경로에 추가하기", use_container_width=True):
                selected_loc = options[selected_address]
                short_name = selected_address.split(',')[0]
                st.session_state.route_data.append({
                    "장소": short_name, "lat": selected_loc.latitude, "lon": selected_loc.longitude
                })
                st.session_state.search_results = [] 
                st.rerun()

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
                folium.Marker(location=coord, popup=row['장소'], icon=icon).add_to(m)
            
            if len(coordinates) > 1:
                folium.PolyLine(locations=coordinates, color='blue', weight=4, opacity=0.7).add_to(m)
            st_folium(m, width=700, height=500)
        else:
            st.info("왼쪽에서 장소를 검색하고 추가하면 지도가 여기에 나타납니다.")

# --- 탭 2: 실시간 환율 적용 경비장 ---
with tab2:
    col_exp_in, col_exp_out = st.columns([1, 2])
    
    with col_exp_in:
        st.subheader("💸 비용 입력")
        e_memo = st.text_input("경비 항목 (예: 왕복 항공권, 점심식사)")
        e_curr = st.selectbox("통화 선택", ["KRW", "USD", "EUR", "JPY", "GBP", "VND"])
        
        # 금액 입력 및 한글 변환
        e_amount = st.number_input("금액 (숫자만 입력)", min_value=0, step=1000)
        
        # 입력한 금액을 읽기 편하게 한국어로 표시 (예: 150만 원)
        if e_amount > 0:
            st.caption(f"💡 입력 금액: **{num_to_kr(e_amount)}**")
        
        if st.button("경비 추가하기", use_container_width=True):
            if e_memo and e_amount > 0:
                rate = get_exchange_rate(e_curr)
                if rate:
                    converted_krw = e_amount * rate
                    new_expense = pd.DataFrame([{
                        "경비 항목": e_memo,
                        "통화": e_curr,
                        "입력금액": f"{e_amount:,.0f}", # 3자리마다 콤마 표시 추가!
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
            total_krw = df['환산금액(원)'].sum()
            st.metric(label="총 예상 경비 (현재 환율 자동 적용)", value=f"{total_krw:,.0f} 원")
            
            st.markdown("#### 📝 상세 내역 수정/삭제")
            st.caption("🗑️ **항목 지우기:** 표의 맨 왼쪽 네모 칸(체크박스)을 누르고, 우측 상단에 생기는 휴지통 아이콘을 누르면 삭제됩니다!")
            
            # num_rows="dynamic" 옵션이 엑셀처럼 항목 삭제/추가를 가능하게 해줍니다.
            edited_df = st.data_editor(df, use_container_width=True, hide_index=False, num_rows="dynamic")
            
            # 표에서 행을 지웠을 때 세션 데이터에도 반영
            st.session_state.expense_data = edited_df
        else:
            st.info("지출 내역을 추가하면 오른쪽에 총합계가 자동 계산되어 표시됩니다.")
