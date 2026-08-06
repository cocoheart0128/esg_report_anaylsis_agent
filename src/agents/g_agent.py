# src/agents/g_agent.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.core.llm_factory import LLMFactory
from src.schemas.agent_schemas import AgentState
from src.services.db_search import search_esg_database # 👈 검색 기능 가져오기

def node_g_agent(state: AgentState):
    print("🏛️ [G Agent] 지배구조 보고서 검색 및 답변 생성 중...")
    
    query_text = state["query"]
    
    # 1. 분리된 검색 함수를 호출하여 데이터만 쏙 가져옴 (self 불필요)
    docs_data = search_esg_database(
        query_text=query_text,
        isu_cd=state.get("isu_cd"),
        year=state.get("year")
    )

    context_str = "\n\n".join(f"[기업명: {d['com_abbrv']}]\n{d['text']}" for d in docs_data)

    # 2. LLM 답변 초안 생성
    llm = LLMFactory.get_llm(provider=state["llm_provider"])
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 기업 지배구조 전문 애널리스트입니다.
        제공된 검색 결과(Context)를 바탕으로 사용자의 질문에 전문적이고 명확하게 답변하세요.
        문서에 없는 내용은 지어내지 마세요.
        
        [Context]
        {context}"""),
        ("human", "{question}")
    ])
    
    answer = (prompt | llm | StrOutputParser()).invoke({"context": context_str, "question": query_text})
    
    return {"draft_answer": answer, "sources": docs_data}