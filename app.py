import streamlit as st
import requests
import os

# 🌟 환경변수에서 API_URL을 가져오고, 없으면 로컬 주소 사용
API_URL = os.getenv("API_URL", "http://localhost:8000/api/analyze")

# 페이지 기본 설정
st.set_page_config(page_title="ESG AI 애널리스트", page_icon="📊", layout="centered")

st.title("📊 ESG AI 애널리스트")
st.markdown("기업의 지배구조 및 ESG 공시 보고서를 심층 분석해 드립니다.")

# ==========================================
# 1. 사이드바 (필터 및 옵션 설정)
# ==========================================
with st.sidebar:
    st.header("🔍 검색 옵션")
    llm_provider = st.selectbox("🤖 LLM 모델 선택", ["gemini", "openai", "claude"])
    
    st.divider()
    st.markdown("**특정 기업/연도 지정 (선택사항)**")
    isu_cd = st.text_input("🏢 종목코드 (6자리)", value="", placeholder="예: 282330")
    year = st.text_input("📅 분석 연도", value="", placeholder="예: 2026")
    
    st.divider()
    st.markdown("""
    **💡 사용 팁**
    * 종목코드와 연도를 비워두면 **DB 전체**를 대상으로 검색합니다.
    * 정확한 분석을 원하시면 종목코드와 연도를 지정해 검색 범위를 좁혀주세요.
    """)

# ==========================================
# 2. 채팅 세션 초기화 및 기록 출력
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 기업 지배구조핵심지표 등 ESG 관련 정보를 물어보세요.", "sources": []}
    ]

# 이전 대화 기록을 화면에 모두 출력 (원본 문서 포함)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # 🌟 저장된 원본 문서(sources)가 있다면 함께 렌더링
        if message.get("sources"):
            with st.expander("🔍 AI가 참고한 원본 공시 문서 확인하기"):
                for i, doc in enumerate(message["sources"]):
                    st.markdown(f"**[{i+1}] {doc.get('com_abbrv', '알수없음')} ({doc.get('eval_year', '알수없음')})** - 유사도 점수: `{doc.get('score', 0):.4f}`")
                    display_text = doc.get('text', '')
                    display_text = display_text if len(display_text) < 500 else display_text[:500] + "..."
                    st.info(display_text)

# ==========================================
# 3. 사용자 채팅 입력 및 API 통신
# ==========================================
if prompt := st.chat_input("질문을 입력하세요 (예: 이사회 안건 요약해 줘)"):
    
    # 사용자가 입력한 메시지를 화면에 표시하고 기록
    st.session_state.messages.append({"role": "user", "content": prompt, "sources": []})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI 답변 대기 화면 (🌟 스피너 대신 에이전트 상태창 사용)
    with st.chat_message("assistant"):
        with st.status("🤖 ESG 에이전트 위원회를 호출합니다...", expanded=True) as status:
            try:
                st.write("🚦 [Router] 질문 의도 분석 및 담당 에이전트 배정 중...")
                
                # FastAPI 서버로 보낼 데이터 묶음
                payload = {
                    "query": prompt,
                    "llm_provider": llm_provider,
                    "isu_cd": isu_cd.strip() if isu_cd else None,
                    "year": year.strip() if year else None
                }
                
                # API 서버로 POST 요청
                response = requests.post(API_URL, json=payload)
                response.raise_for_status()  # 200 OK가 아니면 에러 발생
                
                st.write("🔎 [Specialist] 담당 에이전트가 공시 DB 분석 및 답변 작성 중...")
                
                # 결과 추출
                api_result = response.json()
                
                # 🌟 핵심: main.py에서 'answer' 안에 딕셔너리를 통째로 넣어서 보냈으므로, 
                # 한 번 더 파고 들어가서 진짜 텍스트(answer)와 원본문서(sources)를 꺼냅니다!
                nested_data = api_result.get("answer", {})
                
                if isinstance(nested_data, dict):
                    answer = nested_data.get("answer", "답변을 추출하지 못했습니다.")
                    sources = nested_data.get("sources", [])
                else:
                    # 혹시라도 포장이 안 되어 올 경우를 대비한 방어 코드
                    answer = str(nested_data)
                    sources = api_result.get("sources", [])
                
                # 상태창 업데이트 (완료 시 초록색 체크 표시와 함께 자동으로 접힘)
                status.update(label="분석 완료!", state="complete", expanded=False)
                
                # 1. 화면에 답변 출력
                st.markdown(answer)
                
                # 2. 화면에 원본 문서 토글 버튼 출력
                if sources:
                    with st.expander("🔍 AI가 참고한 원본 공시 문서 확인하기"):
                        for i, doc in enumerate(sources):
                            st.markdown(f"**[{i+1}] {doc.get('com_abbrv', '알수없음')} ({doc.get('eval_year', '알수없음')})** - 유사도 점수: `{doc.get('score', 0):.4f}`")
                            display_text = doc.get('text', '')
                            display_text = display_text if len(display_text) < 500 else display_text[:500] + "..."
                            st.info(display_text)

                # 3. 세션 기록에 답변과 참고 문서 함께 저장
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