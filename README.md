# ESG Report Analysis Agent

ESG 공시보고서와 정형 ESG 등급 데이터를 수집·저장·검색하고, LLM 기반으로 기업의 ESG 관련 질문에 답변하는 통합 분석 시스템입니다.

## 화면 미리보기

<img width="1332" height="871" alt="image" src="https://github.com/user-attachments/assets/22b578e2-c600-48e2-96e1-1a1586b3adf1" />

<img width="1356" height="837" alt="image" src="https://github.com/user-attachments/assets/8ad9ddef-8041-41c6-bc65-d85b8c87aa06" />

<img width="1347" height="861" alt="image" src="https://github.com/user-attachments/assets/a15d5b30-638f-414b-ad3e-9856aea6e67b" />


이 프로젝트는 다음 흐름으로 동작합니다.

1. ETL 파이프라인으로 기업의 ESG 등급 데이터와 공시 문서를 수집합니다.
2. LanceDB에 정형 데이터와 벡터 검색용 문서 청크를 저장합니다.
3. FastAPI 서버가 분석 요청을 받아 RAG 기반 답변을 제공합니다.
4. Streamlit 대시보드에서 기업별 ESG 지표와 AI 챗봇을 함께 확인할 수 있습니다.

---

## 주요 기능

- 기업명 또는 종목코드 기반 ESG 데이터 조회
- 정형 ESG 등급 대시보드 제공
  - KCGS, MSCI, S&P Global, 한국ESG연구소, 서스틴베스트 등
  - 지속가능경영보고서 / 기업지배구조보고서 링크 표시
- AI 기반 ESG 보고서 질의응답
  - LangGraph 기반 다중 에이전트 워크플로우 사용
  - 라우터 에이전트가 질문을 분류하고, 지배구조(G) 관련 질문을 전문적으로 처리
  - 체크 에이전트가 답변의 사실관계와 형식을 검수
- Docker Compose 기반 실행 지원

---

## 프로젝트 구조

```text
.
├── app.py                  # Streamlit 웹 UI 진입점
├── main.py                 # CLI 형태의 샘플 실행 진입점
├── docker-compose.yml      # FastAPI / Streamlit / ETL 서비스 구성
├── Dockerfile              # 컨테이너 이미지 정의
├── requirements.txt        # Python 의존성 목록
├── start.sh                # Docker 실행 스크립트
├── stop.sh                 # Docker 종료 스크립트
├── src/
│   ├── agents/             # Router / G-Agent / ES-Agent / Checker Agent
│   ├── api/                # FastAPI 엔드포인트
│   ├── core/               # LLMFactory
│   ├── etl/                # Extract / Transform / Load 파이프라인
│   ├── schemas/            # 상태 및 라우팅 스키마
│   └── services/           # DB 검색, RAG 서비스
└── data/                   # LanceDB 저장소 및 수집 데이터
```

---

## 기술 스택

- Python 3.10+
- FastAPI
- Streamlit
- LangChain / LangGraph
- LanceDB
- PyArrow
- sentence-transformers
- FinanceDataReader
- Docker Compose

---

## 사전 준비

### 1) Python 환경 구성

```bash
pip install -r requirements.txt
```

### 2) 환경 변수 설정

프로젝트 루트에 .env 파일을 생성하고, 사용할 LLM 제공자에 맞는 API 키를 설정합니다.

```env
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
ANTHROPIC_API_KEY=your_anthropic_key
MODEL_NAME=gemini-1.5-pro
```

> 현재 코드 기준으로 `gemini`, `openai`, `claude` 중 하나를 선택해 사용할 수 있습니다.

---

## 실행 방법

### 방법 A: 로컬 실행

#### 1. FastAPI 서버 실행

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

#### 2. Streamlit 웹 UI 실행

```bash
streamlit run app.py
```

#### 3. ETL 실행

```bash
python -m src.etl.pipeline
```

또는 CLI 형태로 실행할 수도 있습니다.

```bash
python main.py
```

### 방법 B: Docker Compose 실행

```bash
sudo docker compose up -d --build
```

서비스 접속:

- Streamlit UI: http://localhost:8501
- FastAPI Docs: http://localhost:8000/docs

종료:

```bash
sudo docker compose down
```

---

## 사용 흐름

1. Streamlit 화면에서 기업명 또는 종목코드를 입력합니다.
2. 필요 시 ETL 버튼을 눌러 해당 기업의 연도별 ESG 데이터를 수집합니다.
3. 대시보드에서 정형 ESG 등급 정보를 확인합니다.
4. AI 챗봇에 보고서 관련 질문을 입력하면 RAG 기반 답변을 받을 수 있습니다.

---

## 참고 사항

- 현재 구현은 주로 지배구조(G) 관련 분석에 초점을 두고 있습니다.
- 환경(E) 및 사회(S) 관련 질문은 현재 시스템에서 안내형 응답으로 처리됩니다.
- 데이터 저장소는 기본적으로 `data/esg_lancedb` 아래에 생성됩니다.

---

## 라이선스

해당 프로젝트는 내부/실험용으로 구성된 예시 구조이며, 필요 시 서비스 목적에 맞게 확장해 사용할 수 있습니다.
