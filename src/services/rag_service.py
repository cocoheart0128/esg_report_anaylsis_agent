# src/services/rag_service.py
from langgraph.graph import StateGraph, END
from src.schemas.agent_schemas import AgentState

# 🌟 쪼개둔 에이전트 함수들 전부 수입
from src.agents.router import node_router
from src.agents.es_agent import node_es_agent
from src.agents.g_agent import node_g_agent
from src.agents.checker import node_checker

class ESGRagService:
    def __init__(self, db_path="/app/data/esg_lancedb"):
        # 검색 로직이 외부 함수로 빠졌으므로 __init__이 아주 가벼워졌습니다!
        self.workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        
        # 노드 등록 (외부 함수들이므로 self. 안 붙임)
        workflow.add_node("router", node_router)
        workflow.add_node("es_agent", node_es_agent)
        workflow.add_node("g_agent", node_g_agent)
        workflow.add_node("checker", node_checker)
        
        workflow.set_entry_point("router")
        
        # 🌟 조건부 엣지: 질문 의도(domain)에 따라 담당 에이전트로 분기
        workflow.add_conditional_edges(
            "router",
            lambda state: state["domain"],
            {
                "G": "g_agent",           # 기업지배구조보고서 관련 질문
                "ES": "es_agent",         # 지속가능경영보고서(E/S) 관련 질문
                "GENERAL": "g_agent"      # 일반 질문 (기본값으로 g_agent 할당 또는 통합 에이전트로 변경 가능)
            }
        )
        
        # 🌟 [수정된 부분] 지속가능경영보고서(es_agent)도 답변 작성 후 checker를 거치도록 수정
        workflow.add_edge("g_agent", "checker")
        workflow.add_edge("es_agent", "checker") 
        
        # checker가 검수를 마치면 최종 종료
        workflow.add_edge("checker", END)
        
        return workflow.compile()

    def analyze_esg(self, query: str, llm_provider: str, isu_cd: str = None, year: str = None):
        initial_state = {
            "query": query,
            "llm_provider": llm_provider,
            "isu_cd": isu_cd,
            "year": year,
            "domain": "",
            "draft_answer": "",
            "answer": "",
            "sources": []
        }
        
        final_state = self.workflow.invoke(initial_state)
        
        return {
            "answer": final_state.get("answer", "답변을 생성하지 못했습니다."),
            "sources": final_state.get("sources", [])
        }










# # src/services/rag_service.py
# from langgraph.graph import StateGraph, END
# from src.schemas.agent_schemas import AgentState

# # 🌟 쪼개둔 에이전트 함수들 전부 수입
# from src.agents.router import node_router
# from src.agents.es_agent import node_es_agent
# from src.agents.g_agent import node_g_agent
# from src.agents.checker import node_checker

# class ESGRagService:
#     def __init__(self, db_path="/app/data/esg_lancedb"):
#         # 검색 로직이 외부 함수로 빠졌으므로 __init__이 아주 가벼워졌습니다!
#         self.workflow = self._build_graph()

#     def _build_graph(self):
#         workflow = StateGraph(AgentState)
        
#         # 노드 등록 (외부 함수들이므로 self. 안 붙임)
#         workflow.add_node("router", node_router)
#         workflow.add_node("es_agent", node_es_agent)
#         workflow.add_node("g_agent", node_g_agent)
#         workflow.add_node("checker", node_checker)
        
#         workflow.set_entry_point("router")
        
#         workflow.add_conditional_edges(
#             "router",
#             lambda state: state["domain"],
#             {
#                 "G": "g_agent",
#                 "GENERAL": "g_agent",
#                 "ES": "es_agent"
#             }
#         )
        
#         workflow.add_edge("g_agent", "checker")
#         workflow.add_edge("checker", END)
#         workflow.add_edge("es_agent", END)
        
#         return workflow.compile()

#     def analyze_esg(self, query: str, llm_provider: str, isu_cd: str = None, year: str = None):
#         initial_state = {
#             "query": query,
#             "llm_provider": llm_provider,
#             "isu_cd": isu_cd,
#             "year": year,
#             "domain": "",
#             "draft_answer": "",
#             "answer": "",
#             "sources": []
#         }
        
#         final_state = self.workflow.invoke(initial_state)
        
#         return {
#             "answer": final_state["answer"],
#             "sources": final_state["sources"]
#         }





