# src/agents/checker.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.core.llm_factory import LLMFactory
from src.schemas.agent_schemas import AgentState

def node_checker(state: AgentState):
    print("🕵️ [Checker Agent] 초안 팩트체크 및 최종 리포트 서식 다듬는 중...")
    llm = LLMFactory.get_llm(provider=state["llm_provider"], temperature=0.1)

    # 🌟 1. 글자 커짐 방지: 원본 소스 텍스트에서 마크다운 헤더(#) 기호 제거
    clean_sources = []
    for d in state.get("sources", []):
        d_copy = dict(d)
        if "text" in d_copy:
            # '#'이 문장 맨 앞에 오면 H1 제목으로 인식되어 엄청 커지므로 공백으로 치환
            d_copy["text"] = d_copy["text"].replace("#", "") 
        clean_sources.append(d_copy)

    context_str = "\n\n".join(f"[기업명: {d['com_abbrv']}]\n{d.get('text', '')}" for d in clean_sources)

    # 🌟 2. 프롬프트 개선: H1(#), H2(##) 사용 금지 및 글씨 크기 조절 지시
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 엄격한 ESG 팩트체크 검수자이자 전문 에디터입니다.
        1. [초안 답변]이 [원본 데이터]의 내용(수치, 사실관계)과 정확히 일치하는지 검증하세요. 틀린 내용이 있다면 수정하세요.
        2. 사용자에게 보여주기 가장 좋은 형태(깔끔한 마크다운, 명확한 글머리 기호, 필요시 표 사용)로 서식을 디자인하세요.
        3. [중요] 글씨가 너무 크게 나오는 것을 방지하기 위해 제목에 '#'이나 '##'은 절대 사용하지 마세요. 대신 '###'나 '####'를 쓰거나 굵은 글씨(** **)를 활용하세요.
        4. 데이터 구조(JSON 등)를 그대로 노출하지 말고, 읽기 쉬운 완벽한 '보고서' 형태로만 출력하세요.

        [원본 데이터]
        {context}"""),
        ("human", "사용자 질문: {question}\n\n[초안 답변]\n{draft}")
    ])

    final_answer = (prompt | llm | StrOutputParser()).invoke({
        "context": context_str, 
        "question": state["query"], 
        "draft": state["draft_answer"]
    })

    # 🌟 3. 필수: 화면에 출처를 띄우기 위해 sources를 다시 반환 객체에 포함
    return {
        "answer": final_answer,
        "sources": clean_sources
    }