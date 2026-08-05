# src/agents/router.py
from langchain_core.prompts import ChatPromptTemplate
from src.core.llm_factory import LLMFactory
from src.schemas.agent_schemas import AgentState, RouteDecision

def node_router(state: AgentState):
    print(f"\n🚦 [Router Agent] 질문 의도 분석 중... (질문: {state['query']})")
    llm = LLMFactory.get_llm(provider=state["llm_provider"], temperature=0.0)
    router_llm = llm.with_structured_output(RouteDecision)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "당신은 ESG 질문 분류기입니다. 사용자의 질문이 지배구조(G)인지, 환경/사회(ES)인지 분류하세요."),
        ("human", "{query}")
    ])
    
    decision = (prompt | router_llm).invoke({"query": state["query"]})
    print(f"👉 [Router Agent] 분류 결과: {decision.domain}")
    return {"domain": decision.domain}