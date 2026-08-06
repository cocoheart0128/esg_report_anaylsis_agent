import streamlit as st
import requests
import os
import time
import pandas as pd
import FinanceDataReader as fdr  # 🌟 기업명 검색을 위해 추가

# 🌟 DB 로직을 모두 외부(db_search.py)로 빼서 임포트!
from src.services.db_search import get_company_data_years
from src.etl.pipeline import run_etl_pipeline

# API 경로 설정
API_URL = os.getenv("API_URL", "http://localhost:8000/api/analyze")
GRADE_API_URL = API_URL.replace("/analyze", "/grade-info")

# 페이지 기본 설정
st.set_page_config(page_title="ESG AI 애널리스트", page_icon="📊", layout="wide")

st.title("📊 ESG 통합 대시보드 & AI 애널리스트")
st.markdown("기업의 정형 ESG 등급 지표 및 공시 보고서를 심층 분석해 드립니다.")

# ==========================================
# 🌟 0. 한국거래소(KRX) 상장종목 데이터 로드 (캐싱 적용으로 속도 최적화)
# ==========================================
@st.cache_data
def load_company_list():
    """KRX 상장 기업 목록을 1번만 가져와서 캐싱해 둡니다."""
    try:
        df = fdr.StockListing('KRX')
        return df[['Name', 'Code']]
    except Exception as e:
        st.error(f"주식 종목 데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame(columns=['Name', 'Code'])

company_df = load_company_list()

# ==========================================
# 1. 사이드바 (설정 및 상시 데이터 수집기)
# ==========================================
with st.sidebar:
    st.header("🔍 검색 및 데이터 관리")
    llm_provider = st.selectbox("🤖 LLM 모델 선택", ["gemini", "openai", "claude"])
    
    st.divider()
    
    # 🌟 1. 기업 검색 (이름 or 코드)
    st.markdown("🎯 **1. 기업 검색**")
    search_keyword = st.text_input("🏢 기업명 또는 종목코드", value="", placeholder="예: 카카오 또는 035720")
    
    # 내부적으로 사용할 6자리 종목코드 변수 초기화
    isu_cd = ""
    
    # 입력값이 있을 때 이름 -> 코드로 변환 로직 수행
    if search_keyword:
        if search_keyword.isdigit() and len(search_keyword) == 6:
            # 6자리 숫자면 그대로 종목코드로 인식
            isu_cd = search_keyword
        else:
            # 문자열(기업명)이면 종목코드 검색
            match = company_df[company_df['Name'] == search_keyword]
            if not match.empty:
                isu_cd = match.iloc[0]['Code']
                st.success(f"✅ 인식 완료: {search_keyword} ({isu_cd})")
            else:
                st.error("❌ 정확한 상장 기업명을 입력해주세요. (예: 삼성전자)")

    st.divider()

    st.markdown("⚙️ **2. 데이터 추가 수집 (ETL)**")
    st.caption("※ DB에 없는 연도의 데이터를 추가로 수집합니다.")
    
    col1, col2 = st.columns(2)
    with col1:
        etl_start_year = st.text_input("수집 시작 연도", value="2024")
    with col2:
        etl_end_year = st.text_input("수집 종료 연도", value="2026")

    if st.button("🚀 데이터 수집 실행", use_container_width=True):
        if not isu_cd:
            st.error("유효한 기업명이나 종목코드를 먼저 입력해주세요!")
        else:
            with st.spinner(f"'{search_keyword}({isu_cd})' 기업의 {etl_start_year}~{etl_end_year}년 데이터를 수집 중입니다... (몇 분 소요)"):
                try:
                    run_etl_pipeline(
                        start_yr=etl_start_year.strip(), 
                        end_yr=etl_end_year.strip(), 
                        isu_cd=isu_cd.strip()
                    )
                    st.success("✅ 수집이 완료되었습니다! 화면을 새로고침하여 대시보드에 연도를 추가합니다.")
                    time.sleep(2)
                    st.rerun() 
                except Exception as e:
                    st.error(f"🚨 수집 중 오류 발생: {e}")

    st.divider()
    
    st.markdown("🤖 **3. AI 챗봇 분석 필터**")
    st.caption("※ 챗봇 질문 시 특정 연도만 타겟팅하려면 입력하세요. (비워두면 보유한 전체 기간 대상)")
    analysis_year = st.text_input("📅 AI 분석 연도 (선택)", value="", placeholder="예: 2026")

# ==========================================
# 2. 상단 영역: 모던 2열 레이아웃 대시보드 & 챗봇 렌더링
# ==========================================

# 🌟 화면 좌우 분할 (비율: 왼쪽 대시보드 1.1 : 오른쪽 채팅 0.9)

# ==========================================
# [좌측 컬럼] 정형 ESG 핵심 지표 대시보드
# ==========================================

st.markdown("### 📈 정형 ESG 핵심 지표 대시보드")

available_years = []

if not isu_cd:
    st.info("💡 좌측 사이드바에 **기업명(예: 카카오) 또는 종목코드(6자리)**를 입력하시면 데이터를 조회합니다.")
else:
    available_years = get_company_data_years(isu_cd=isu_cd.strip())
    
    if not available_years:
        st.warning(f"⚠️ DB에 '{search_keyword}({isu_cd})' 기업의 데이터가 없습니다. 좌측 사이드바의 **[🚀 데이터 수집 실행]** 버튼을 눌러주세요.")
    else:
        selected_dash_year = st.selectbox("📊 대시보드 조회 연도 선택 (DB 보유 데이터)", available_years)
        
        with st.spinner(f"{selected_dash_year}년 정형 데이터를 불러오는 중..."):
            try:
                params = {
                    "isu_cd": isu_cd.strip(),
                    "year": selected_dash_year
                }
                    
                grade_res = requests.get(GRADE_API_URL, params=params)
                
                if grade_res.status_code == 200:
                    data = grade_res.json()
                    
                    # 기업 타이틀 카드 스타일
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 12px 16px; border-radius: 10px; margin-bottom: 15px; border-left: 5px solid #1f77b4;">
                        <h4 style="margin: 0; color: #333; font-size: 16px;">🏢 {data.get('com_abbrv', '알수없음')} <span style="font-size: 13px; color: #666;">({data.get('isu_cd', isu_cd)})</span></h4>
                        <p style="margin: 3px 0 0 0; font-size: 12px; color: #555;">기준 연도: <b>{data.get('target_year', selected_dash_year)}년</b></p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 세련된 슬림 카드 함수
                    def make_card(title, grade, sub_text, bg_color="#ffffff"):
                        color = "#2b6cb0" if grade not in ["-", ""] else "#a0aec0"
                        return f"""
                        <div style="background-color: {bg_color}; padding: 10px 8px; border-radius: 10px; 
                                    border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 10px;">
                            <p style="margin: 0; font-size: 12px; color: #4a5568; font-weight: 600;">{title}</p>
                            <h3 style="margin: 5px 0; color: {color}; font-size: 20px; font-weight: 700;">{grade}</h3>
                            <p style="margin: 0; font-size: 10px; color: #a0aec0;">{sub_text}</p>
                        </div>
                        """

                    st.markdown("<p style='font-size: 14px; font-weight: bold; color: #2d3748; margin-bottom: 5px;'>📌 한국ESG기준원 (KCGS) 평가</p>", unsafe_allow_html=True)
                    kcgs = data.get("kcgs", {})
                    k_yy = f"{kcgs.get('year', '-')}년 평가" if kcgs.get('year') else "데이터 없음"
                    
                    c1, c2, c3, c4 = st.columns(4)
                    with c1: st.markdown(make_card("KCGS 종합", kcgs.get("esg", "-"), k_yy, bg_color="#ebf8ff"), unsafe_allow_html=True)
                    with c2: st.markdown(make_card("환경 (E)", kcgs.get("env", "-"), "Environment"), unsafe_allow_html=True)
                    with c3: st.markdown(make_card("사회 (S)", kcgs.get("soc", "-"), "Social"), unsafe_allow_html=True)
                    with c4: st.markdown(make_card("지배구조 (G)", kcgs.get("gov", "-"), "Governance"), unsafe_allow_html=True)

                    st.markdown("<p style='font-size: 14px; font-weight: bold; color: #2d3748; margin: 10px 0 5px 0;'>📌 글로벌 및 기타 평가기관</p>", unsafe_allow_html=True)
                    c5, c6, c7, c8 = st.columns(4)
                    with c5:
                        msci = data.get("msci", {})
                        st.markdown(make_card("MSCI", msci.get("esg", "-"), f"{msci.get('year', '-')}년"), unsafe_allow_html=True)
                    with c6:
                        sp = data.get("sp", {})
                        st.markdown(make_card("S&P Global", sp.get("esg", "-"), f"{sp.get('year', '-')}년"), unsafe_allow_html=True)
                    with c7:
                        kesg = data.get("kesg", {})
                        st.markdown(make_card("한국ESG연구소", kesg.get("esg", "-"), f"{kesg.get('year', '-')}년"), unsafe_allow_html=True)
                    with c8:
                        sv = data.get("sv", {})
                        st.markdown(make_card("서스틴베스트", sv.get("esg", "-"), f"{sv.get('year', '-')}년"), unsafe_allow_html=True)

                    # 공시 보고서 여부 카드 영역
                    st.markdown("<p style='font-size: 14px; font-weight: bold; color: #2d3748; margin: 10px 0 5px 0;'>📑 공식 공시 보고서 제출 여부</p>", unsafe_allow_html=True)
                    
                    reports = data.get("reports", {})
                    r1, r2 = st.columns(2)
                    
                    def make_report_card(title, url, acpt_no):
                        if url and url != "None":
                            color = "#319795" 
                            status_text = "YES"
                            sub_info = f"접수: {acpt_no}"
                            return f"""
                            <div style="background-color: #ffffff; padding: 10px; border-radius: 10px; 
                                        border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 5px;">
                                <p style="margin: 0; font-size: 12px; color: #4a5568; font-weight: bold;">{title}</p>
                                <div style="margin: 6px 0;">
                                    <a href="{url}" target="_blank" style="background-color: {color}; color: white; padding: 3px 14px; 
                                        border-radius: 12px; text-decoration: none; font-weight: bold; font-size: 13px; display: inline-block;">
                                        {status_text}
                                    </a>
                                </div>
                                <p style="margin: 0; font-size: 9px; color: #a0aec0;">{sub_info} (클릭시 원본열기)</p>
                            </div>
                            """
                        else:
                            color = "#cbd5e0"
                            status_text = "NO"
                            sub_info = "미제출 또는 데이터 없음"
                            return f"""
                            <div style="background-color: #f7fafc; padding: 10px; border-radius: 10px; 
                                        border: 1px solid #e2e8f0; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.02); margin-bottom: 5px;">
                                <p style="margin: 0; font-size: 12px; color: #a0aec0; font-weight: bold;">{title}</p>
                                <div style="margin: 6px 0;">
                                    <span style="background-color: {color}; color: white; padding: 3px 14px; 
                                            border-radius: 12px; font-weight: bold; font-size: 13px; display: inline-block;">
                                        {status_text}
                                    </span>
                                </div>
                                <p style="margin: 0; font-size: 9px; color: #cbd5e0;">{sub_info}</p>
                            </div>
                            """

                    with r1:
                        s_rep = reports.get("sustainable_report", {})
                        st.markdown(make_report_card("지속가능경영보고서", s_rep.get("url"), s_rep.get("acpt_no")), unsafe_allow_html=True)
                    with r2:
                        g_rep = reports.get("governance_report", {})
                        st.markdown(make_report_card("기업지배구조보고서", g_rep.get("url"), g_rep.get("acpt_no")), unsafe_allow_html=True)
                        
                else:
                    st.warning(f"⚠️ {selected_dash_year}년의 정형 ESG 등급 데이터를 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"🚨 정형 데이터 연동 중 오류 발생: {str(e)}")


st.divider()

# ==========================================
# [우측 컬럼] AI 공시 보고서 심층 질의응답 (정석 패널 박스 적용)
# ==========================================

st.subheader("💬 AI 공시 보고서 심층 질의응답")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 보고서에 있는 ESG 관련 정보를 물어보세요.", "sources": []}
    ]

# 🌟 st.container에 border=True를 주면 테두리 박스가 깔끔하게 생성됩니다!
with st.container(border=True):
    
    # 내부 대화 내용 출력
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("🔍 AI가 참고한 원본 공시 문서 확인하기"):
                    for i, doc in enumerate(message["sources"]):
                        st.markdown(f"**[{i+1}] {doc.get('com_abbrv', '알수없음')} ({doc.get('eval_year', '알수없음')})** - 유사도 점수: `{doc.get('score', 0):.4f}`")
                        display_text = doc.get('text', '')
                        display_text = display_text if len(display_text) < 400 else display_text[:400] + "..."
                        st.info(display_text)

    # 사용자 채팅 입력 및 RAG API 통신
    if (not isu_cd) or available_years:
        if prompt := st.chat_input("질문을 입력하세요 (예: 이사회 안건 요약해 줘)"):
            
            st.session_state.messages.append({"role": "user", "content": prompt, "sources": []})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.status("🤖 ESG 에이전트 위원회를 호출합니다...", expanded=True) as status:
                    try:
                        st.write("🚦 [Router] 질문 의도 분석 및 담당 에이전트 배정 중...")
                        
                        payload = {
                            "query": prompt,
                            "llm_provider": llm_provider,
                            "isu_cd": isu_cd.strip() if isu_cd else None,
                            "year": analysis_year.strip() if analysis_year else None
                        }
                        
                        response = requests.post(API_URL, json=payload)
                        response.raise_for_status()
                        
                        st.write("🔎 [Specialist] 담당 에이전트가 공시 DB 분석 및 답변 작성 중...")
                        api_result = response.json()
                        
                        nested_data = api_result.get("answer", {})
                        if isinstance(nested_data, dict):
                            answer = nested_data.get("answer", "답변을 추출하지 못했습니다.")
                            sources = nested_data.get("sources", [])
                        else:
                            answer = str(nested_data)
                            sources = api_result.get("sources", [])
                        
                        status.update(label="분석 완료!", state="complete", expanded=False)
                        st.markdown(answer)
                        
                        if sources:
                            with st.expander("🔍 AI가 참고한 원본 공시 문서 확인하기"):
                                for i, doc in enumerate(sources):
                                    st.markdown(f"**[{i+1}] {doc.get('com_abbrv', '알수없음')} ({doc.get('eval_year', '알수없음')})** - 유사도 점수: `{doc.get('score', 0):.4f}`")
                                    display_text = doc.get('text', '')
                                    display_text = display_text if len(display_text) < 400 else display_text[:400] + "..."
                                    st.info(display_text)

                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": answer,
                            "sources": sources
                        })
                        
                    except requests.exceptions.ConnectionError:
                        status.update(label="서버 연결 실패", state="error", expanded=True)
                        error_msg = "🚨 API 서버에 연결할 수 없습니다. FastAPI 서버가 실행 중인지 확인해 주세요."
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg, "sources": []})
                    except Exception as e:
                        status.update(label="분석 오류 발생", state="error", expanded=True)
                        error_msg = f"🚨 분석 중 오류가 발생했습니다: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg, "sources": []})

st.divider()