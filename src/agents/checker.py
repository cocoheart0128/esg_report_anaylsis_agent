# src/agents/checker.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.core.llm_factory import LLMFactory
from src.schemas.agent_schemas import AgentState

def node_checker(state: AgentState):
    print("🕵️ [Checker Agent] 초안 팩트체크 및 최종 리포트 서식 다듬는 중...")
    llm = LLMFactory.get_llm(provider=state["llm_provider"], temperature=0.1)
    
    context_str = "\n\n".join(f"[기업명: {d['com_abbrv']}]\n{d['text']}" for d in state["sources"])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 엄격한 ESG 팩트체크 검수자이자 전문 에디터입니다.
        1. [초안 답변]이 [원본 데이터]의 내용(수치, 사실관계)과 정확히 일치하는지 검증하세요. 틀린 내용이 있다면 수정하세요.
        2. 사용자에게 보여주기 가장 좋은 형태(깔끔한 마크다운, 명확한 글머리 기호, 필요시 표 사용)로 서식을 완전히 새롭게 디자인하여 최종 답변을 작성하세요.
        3. 데이터 구조(JSON 등)를 그대로 노출하지 말고, 읽기 쉬운 완벽한 '보고서' 형태로만 출력하세요.
        
        [원본 데이터]
        {context}"""),
        ("human", "사용자 질문: {question}\n\n[초안 답변]\n{draft}")
    ])
    
    final_answer = (prompt | llm | StrOutputParser()).invoke({
        "context": context_str, 
        "question": state["query"], 
        "draft": state["draft_answer"]
    })
    
    return {"answer": final_answer}