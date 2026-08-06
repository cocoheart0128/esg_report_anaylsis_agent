# src/agents/es_agent.py
from src.schemas.agent_schemas import AgentState

def node_es_agent(state: AgentState):
    print("🌿 [E/S Agent] 지속가능경영(환경/사회) 안내 멘트 생성 중...")
    fallback_msg = (
        "요청하신 내용은 **환경(E) 및 사회(S) 관련 지속가능경영 분야**입니다.\n\n"
        "현재 시스템은 1단계 구축 중으로 **'지배구조(G)'** 관련 데이터만 분석이 가능합니다. "
        "빠른 시일 내에 환경 및 사회 데이터 파이프라인을 연결하여 답변드릴 수 있도록 하겠습니다."
    )
    return {"answer": fallback_msg, "sources": []}