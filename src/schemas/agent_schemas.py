from typing import TypedDict, List, Dict, Optional
from pydantic import BaseModel, Field
# ==========================================
# 1. 상태(State) 및 구조화된 출력(Schema) 정의
# ==========================================
class AgentState(TypedDict):
    """에이전트들이 서로 주고받을 데이터 상태창고"""
    query: str
    llm_provider: str
    isu_cd: Optional[str]
    year: Optional[str]
    domain: str              # 라우터가 결정한 도메인 (G, ES, GENERAL)
    draft_answer: str
    answer: str              # 최종 답변
    sources: List[Dict]      # 검색된 참고 문서

class RouteDecision(BaseModel):
    """라우터 에이전트가 무조건 이 형태로만 대답하도록 강제하는 스키마 (Structured Output)"""
    domain: str = Field(
        description="질문의 도메인. 다음 중 하나만 출력: 'G'(지배구조, 이사회, 주주, 배당, 감사), 'ES'(환경, 기후, 탄소, 사회, 임직원, 안전), 'GENERAL'(단순 인사나 일반 대화)"
    )
