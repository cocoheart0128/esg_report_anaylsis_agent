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
        
        workflow.add_conditional_edges(
            "router",
            lambda state: state["domain"],
            {
                "G": "g_agent",
                "GENERAL": "g_agent",
                "ES": "es_agent"
            }
        )
        
        workflow.add_edge("g_agent", "checker")
        workflow.add_edge("checker", END)
        workflow.add_edge("es_agent", END)
        
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
            "answer": final_state["answer"],
            "sources": final_state["sources"]
        }






# import lancedb
# from langgraph.graph import StateGraph, END
# from langchain_community.vectorstores import LanceDB
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import StrOutputParser
# from src.core.llm_factory import LLMFactory
# from src.schemas.agent_schemas import AgentState,RouteDecision


# class ESGRagService:
#     def __init__(self, db_path="/app/data/esg_lancedb"):
#         # 임베딩 및 DB 세팅 (기존과 동일)
#         self.embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
#         self.db = lancedb.connect(db_path)
#         self.table = self.db.open_table("tb_esg_corp_gov_report")
        
#         try:
#             self.table.create_fts_index("text", replace=False)
#             print("✅ FTS(Full Text Search) 인덱스 생성 완료")
#         except Exception:
#             pass

#         # 🌟 LangGraph 멀티 에이전트 워크플로우 빌드
#         self.workflow = self._build_graph()

#     # ==========================================
#     # 2. 에이전트 노드(Node) 정의
#     # ==========================================
#     def node_router(self, state: AgentState):
#         """[라우터 에이전트] 질문을 분석하여 방향을 결정합니다."""
#         print(f"\n🚦 [Router Agent] 질문 의도 분석 중... (질문: {state['query']})")
#         llm = LLMFactory.get_llm(provider=state["llm_provider"], temperature=0.0)
        
#         # LLM에게 구조화된 출력(Pydantic)을 강제합니다.
#         router_llm = llm.with_structured_output(RouteDecision)
        
#         prompt = ChatPromptTemplate.from_messages([
#             ("system", "당신은 ESG 질문 분류기입니다. 사용자의 질문이 지배구조(G)인지, 환경/사회(ES)인지 분류하세요."),
#             ("human", "{query}")
#         ])
        
#         chain = prompt | router_llm
#         decision = chain.invoke({"query": state["query"]})
        
#         print(f"👉 [Router Agent] 분류 결과: {decision.domain}")
#         return {"domain": decision.domain}

#     def node_es_agent(self, state: AgentState):
#         """[E/S 에이전트] 아직 데이터가 없으므로 정중하게 거절합니다."""
#         print("🌿 [E/S Agent] 지속가능경영(환경/사회) 안내 멘트 생성 중...")
#         fallback_msg = (
#             "요청하신 내용은 **환경(E) 및 사회(S) 관련 지속가능경영 분야**입니다.\n\n"
#             "현재 시스템은 1단계 구축 중으로 **'지배구조(G)'** 관련 데이터만 분석이 가능합니다. "
#             "빠른 시일 내에 환경 및 사회 데이터 파이프라인을 연결하여 답변드릴 수 있도록 하겠습니다."
#         )
#         return {"answer": fallback_msg, "sources": []}

#     def node_g_agent(self, state: AgentState):
#         """[G 에이전트] 지배구조 데이터를 검색하고 실질적인 답변을 생성합니다."""
#         print("🏛️ [G Agent] 지배구조 보고서 검색 및 답변 생성 중...")
        
#         # 1. DB 검색 준비
#         filters = []
#         if state["isu_cd"]: filters.append(f"isu_cd = '{state['isu_cd']}'")
#         if state["year"]: filters.append(f"eval_year = {state['year']}")
#         filter_str = " AND ".join(filters) if filters else None

#         query_text = state["query"]
#         query_vector = self.embeddings.embed_query(query_text)

#         # 2. 하이브리드 검색 실행
#         search_req = self.table.search(query_type="hybrid").vector(query_vector).text(query_text).limit(10)
#         if filter_str:
#             search_req = search_req.where(filter_str, prefilter=True)
            
#         results = search_req.to_list()
        
#         docs_data = []
#         for res in results:
#             docs_data.append({
#                 "com_abbrv": res.get("com_abbrv", "알수없음"),
#                 "eval_year": res.get("eval_year", "알수없음"),
#                 "text": res.get("text", ""),
#                 "score": res.get("_distance", res.get("score", res.get("_score", 0.0)))
#             })

#         context_str = "\n\n".join(f"[기업명: {d['com_abbrv']}]\n{d['text']}" for d in docs_data)

#         # 3. LLM 답변 생성
#         llm = LLMFactory.get_llm(provider=state["llm_provider"])
#         prompt = ChatPromptTemplate.from_messages([
#             ("system", """당신은 기업 지배구조 전문 애널리스트입니다.
#             제공된 검색 결과(Context)를 바탕으로 사용자의 질문에 전문적이고 명확하게 답변하세요.
#             문서에 없는 내용은 지어내지 마세요.
            
#             [Context]
#             {context}"""),
#             ("human", "{question}")
#         ])
        
#         chain = prompt | llm | StrOutputParser()
#         answer = chain.invoke({"context": context_str, "question": query_text})
        
#         return {"draft_answer": answer, "sources": docs_data}

#     # ==========================================
#     # 🌟 추가된 에이전트: 팩트체크 및 포맷팅 전문 검수자
#     # ==========================================
#     def node_checker(self, state: AgentState):
#         print("🕵️ [Checker Agent] 초안 팩트체크 및 최종 리포트 서식 다듬는 중...")
#         llm = LLMFactory.get_llm(provider=state["llm_provider"], temperature=0.1) # 팩트체크용이므로 온도 낮춤
        
#         context_str = "\n\n".join(f"[기업명: {d['com_abbrv']}]\n{d['text']}" for d in state["sources"])
        
#         prompt = ChatPromptTemplate.from_messages([
#             ("system", """당신은 엄격한 ESG 팩트체크 검수자이자 전문 에디터입니다.
#             1. [초안 답변]이 [원본 데이터]의 내용(수치, 사실관계)과 정확히 일치하는지 검증하세요. 틀린 내용이 있다면 수정하세요.
#             2. 사용자에게 보여주기 가장 좋은 형태(깔끔한 마크다운, 명확한 글머리 기호, 필요시 표 사용)로 서식을 완전히 새롭게 디자인하여 최종 답변을 작성하세요.
#             3. 데이터 구조(JSON 등)를 그대로 노출하지 말고, 읽기 쉬운 완벽한 '보고서' 형태로만 출력하세요.
            
#             [원본 데이터]
#             {context}"""),
#             ("human", "사용자 질문: {question}\n\n[초안 답변]\n{draft}")
#         ])
        
#         final_answer = (prompt | llm | StrOutputParser()).invoke({
#             "context": context_str, 
#             "question": state["query"], 
#             "draft": state["draft_answer"]
#         })
        
#         return {"answer": final_answer}

#     # ==========================================
#     # 3. 그래프(Workflow) 조립
#     # ==========================================
#     def _build_graph(self):
#         workflow = StateGraph(AgentState)
        
#         # 노드 추가
#         workflow.add_node("router", self.node_router)
#         workflow.add_node("g_agent", self.node_g_agent)
#         workflow.add_node("checker", self.node_checker) # 🌟 검수자 노드 추가
#         workflow.add_node("es_agent", self.node_es_agent)
        
#         # 시작점 설정
#         workflow.set_entry_point("router")
        
#         # 조건부 라우팅 (Router의 결과에 따라 어디로 갈지 결정)
#         workflow.add_conditional_edges(
#             "router",
#             lambda state: state["domain"], # 상태의 domain 값에 따라 분기
#             {
#                 "G": "g_agent",
#                 "GENERAL": "g_agent", # 일반 질문도 일단 G-Agent가 처리
#                 "ES": "es_agent"
#             }
#         )
        
#         # 종료점 연결
#         workflow.add_edge("g_agent", "checker")
#         workflow.add_edge("checker", END)
#         workflow.add_edge("es_agent", END)
        
#         return workflow.compile()

#     # ==========================================
#     # 4. 최종 실행 메서드 (FastAPI가 호출함)
#     # ==========================================
#     def analyze_esg(self, query: str, llm_provider: str, isu_cd: str = None, year: str = None):
#         # LangGraph에 던질 초기 상태값
#         initial_state = {
#             "query": query,
#             "llm_provider": llm_provider,
#             "isu_cd": isu_cd,
#             "year": year,
#             "domain": "",
#             "draft_answer": "", # 🌟 (여기도 꼭 추가해 주세요!)
#             "answer": "",
#             "sources": []
#         }
        
#         # 그래프 실행
#         final_state = self.workflow.invoke(initial_state)
        
#         # FastAPI 서버로 최종 결과(답변 + 원본 문서) 반환
#         return {
#             "answer": final_state["answer"],
#             "sources": final_state["sources"]
#         }