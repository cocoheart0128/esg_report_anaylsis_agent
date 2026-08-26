"""
db_search 레거시에서 새 버전으로의 마이그레이션 가이드

기존 코드가 계속 작동하도록 하위 호환성을 제공하지만,
새 프로젝트는 새 구조를 사용하기를 권장합니다.
"""

# ============================================================================
# 📋 개선사항 요약
# ============================================================================
"""
1. ✅ 설정 중앙화
   - 모든 상수를 database_config.py에 통합
   - 환경 자동 감지 (Docker, Cloud, 로컬)
   - 싱글톤 패턴으로 인스턴스 관리

2. ✅ 타입 안전성 강화
   - Pydantic 모델로 모든 응답 검증
   - 명확한 반환 타입 정의
   - IDE 자동완성 지원

3. ✅ 에러 처리 일관화
   - 커스텀 Exception 클래스 정의
   - 구조화된 에러 메시지
   - 실패해도 응답은 일관된 구조

4. ✅ 성능 최적화
   - 임베딩 모델 싱글톤 캐싱
   - DB 연결 캐싱
   - 중복 로직 제거

5. ✅ 운영성 개선
   - logging 통합 (print 제거)
   - 상세한 로그 메시지
   - 검색 모드 추적 (hybrid/vector)

6. ✅ 유지보수성 향상
   - 코드 분리 (설정, 스키마, 서비스)
   - 명확한 함수 문서화
   - 헬퍼 메서드로 중복 제거

7. ✅ 테스트 용이성
   - 의존성 주입 가능
   - 싱글톤 리셋 함수 제공
   - 모의 객체 생성 용이
"""


# ============================================================================
# 🔄 마이그레이션 방법
# ============================================================================

"""
[방법 1] 최소한의 변경 (기존 코드 그대로 사용)
─────────────────────────────────────────────────────
기존 코드가 있으면 변경 없이 그대로 작동합니다.
(하위호환성 함수가 제공됨)

OLD:
    from src.services.db_search import search_esg_database
    
    results = search_esg_database(query_text="탄소중립", isu_cd="000913")
    for res in results:
        print(res['com_abbrv'], res['text'])

NEW:
    # 코드 변경 없음! 그대로 작동합니다
    from src.services.db_search_v2 import search_esg_database
    
    results = search_esg_database(query_text="탄소중립", isu_cd="000913")
    for res in results:
        print(res['com_abbrv'], res['text'])


[방법 2] 권장: 새로운 서비스 클래스 사용 (프로덕션)
─────────────────────────────────────────────────────
더 나은 에러 처리와 기능을 활용할 수 있습니다.

OLD:
    from src.services.db_search import search_esg_database
    
    results = search_esg_database(query_text="탄소중립")
    for res in results:
        print(f"Score: {res['score']}")

NEW (권장):
    from src.services.db_search_v2 import ESGSearchService
    
    service = ESGSearchService()
    response = service.search_esg_reports(query_text="탄소중립")
    
    if response.success:
        for result in response.results:
            print(f"Score: {result.score:.2f}")
            print(f"Company: {result.company}")
            print(f"Text: {result.text}")
    else:
        print(f"Error: {response.message}")


[방법 3] FastAPI에서 사용 (API 서버)
─────────────────────────────────────────────────────
from fastapi import FastAPI
from src.services.db_search_v2 import ESGSearchService

app = FastAPI()
search_service = ESGSearchService()

@app.post("/api/search")
def search(query: str, isu_cd: str = None, year: str = None):
    response = search_service.search_esg_reports(
        query_text=query,
        isu_cd=isu_cd,
        year=year
    )
    return response.dict()

@app.get("/api/grade/{isu_cd}")
def get_grade(isu_cd: str, year: str = None):
    response = search_service.get_esg_grade(isu_cd, year)
    return response.dict()

@app.get("/api/years/{isu_cd}")
def get_years(isu_cd: str):
    response = search_service.get_available_years(isu_cd)
    return response.dict()
"""


# ============================================================================
# 📊 코드 비교
# ============================================================================

"""
┌─────────────────────────────────────────────────────────────────────────┐
│ 기존 코드 (db_search.py)                                               │
├─────────────────────────────────────────────────────────────────────────┤
│ ❌ 설정: 상수가 여러 파일에 흩어짐                                     │
│ ❌ 반환값: dict 딕셔너리만 반환 (타입 불명확)                          │
│ ❌ 에러: print()로만 처리, 일관성 없음                                  │
│ ❌ 성능: 함수 호출마다 임베딩 모델 로딩                                │
│ ❌ 로깅: print() 사용 (프로덕션 부적합)                                 │
│ ❌ 문서: Docstring 미흡                                                 │
│ ❌ 중복: 필터 로직이 여러 함수에서 반복                                │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ 새 코드 (db_search_v2.py)                                               │
├─────────────────────────────────────────────────────────────────────────┤
│ ✅ 설정: DatabaseConfig 클래스 (중앙화)                                 │
│ ✅ 반환값: Pydantic 모델 (타입 안전)                                    │
│ ✅ 에러: 커스텀 Exception 클래스 (구조화됨)                            │
│ ✅ 성능: 싱글톤 + 캐싱 (최적화됨)                                      │
│ ✅ 로깅: logging 모듈 (프로덕션 표준)                                  │
│ ✅ 문서: 상세한 Docstring                                              │
│ ✅ 중복: 헬퍼 메서드로 DRY 원칙 준수                                   │
└─────────────────────────────────────────────────────────────────────────┘
"""


# ============================================================================
# 🔧 설정 커스터마이징 예제
# ============================================================================

"""
[예제 1] 커스텀 DB 경로 사용
───────────────────────────

from src.config.database_config import DatabaseConfig
from src.services.db_search_v2 import ESGSearchService

# 커스텀 설정 생성
config = DatabaseConfig(db_path="/custom/path/esg_lancedb")

# 서비스 생성 (주의: 싱글톤이므로 한 번만 생성 권장)
service = ESGSearchService()

# 이제 service는 커스텀 경로를 사용합니다


[예제 2] 테스트를 위한 설정 초기화
──────────────────────────────────

from src.config.database_config import reset_db_config
from src.services.db_search_v2 import ESGSearchService

# 캐시된 설정 초기화
reset_db_config()

# 새로운 설정으로 서비스 재생성
service = ESGSearchService()


[예제 3] 검색 결과를 JSON으로 변환
───────────────────────────────────

from src.services.db_search_v2 import ESGSearchService
import json

service = ESGSearchService()
response = service.search_esg_reports(query_text="탄소중립")

# Pydantic 모델을 JSON으로 변환
json_str = response.model_dump_json(indent=2, by_alias=True)
print(json_str)

# 또는 dict로 변환
json_dict = response.model_dump(by_alias=True)
"""


# ============================================================================
# 🧪 테스트 예제
# ============================================================================

"""
from src.services.db_search_v2 import ESGSearchService

# [테스트 1] 검색 기능
service = ESGSearchService()

# 하이브리드 검색 (또는 벡터 폴백)
response = service.search_esg_reports(
    query_text="환경 정책",
    isu_cd="000913",
    year="2024",
    limit=5
)

assert response.success, f"검색 실패: {response.message}"
assert len(response.results) > 0, "검색 결과가 없음"
assert response.search_mode in ["hybrid", "vector"], "검색 모드 오류"

# 각 결과가 SearchResult 타입인지 확인
for result in response.results:
    assert hasattr(result, 'company'), "company 속성 없음"
    assert hasattr(result, 'score'), "score 속성 없음"
    assert 0 <= result.score <= 1, "score 범위 오류"

print(f"✅ 검색 테스트 통과 ({response.search_mode})")


# [테스트 2] ESG 등급 조회
response = service.get_esg_grade(isu_cd="000913", year="2024")

if response.success and response.data:
    assert response.data.isu_cd == "000913", "종목코드 오류"
    assert response.data.target_year == "2024", "연도 오류"
    print(f"✅ ESG 등급 조회 성공: {response.data.com_abbrv}")
else:
    print(f"⚠️ ESG 등급 조회 실패: {response.message}")


# [테스트 3] 사용 가능한 연도 조회
response = service.get_available_years(isu_cd="000913")

if response.success:
    assert isinstance(response.years, list), "years는 리스트여야 함"
    print(f"✅ 사용 가능한 연도: {', '.join(response.years)}")
else:
    print(f"⚠️ 연도 조회 실패: {response.message}")
"""


# ============================================================================
# 📝 파일 구조
# ============================================================================

"""
src/
├── config/
│   └── database_config.py          # ✨ 새로 추가
│       └── DatabaseConfig 클래스 (설정 중앙화)
│       └── get_db_config() 함수 (싱글톤)
│
├── schemas/
│   ├── agent_schemas.py            # 기존
│   └── search_schemas.py            # ✨ 새로 추가
│       └── SearchResult (Pydantic 모델)
│       └── SearchResponse (응답 구조)
│       └── ESGGrade (등급 데이터)
│       └── 커스텀 Exception 클래스들
│
├── services/
│   ├── db_search.py                # 기존 (하위호환성)
│   └── db_search_v2.py             # ✨ 새로 추가 (권장)
│       └── ESGSearchService 클래스 (메인 서비스)
│       └── 하위호환성 래퍼 함수들
│
└── ... (기타)
"""


# ============================================================================
# ⚡ 성능 개선
# ============================================================================

"""
┌──────────────────────────────────────────────────────────────────────┐
│ 임베딩 모델 캐싱의 중요성                                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 기존:  search_esg_database() 호출마다                              │
│        → HuggingFaceEmbeddings 로드 (매번 ~2초)                   │
│        → 100회 검색 시: ~200초 소요 ❌                             │
│                                                                      │
│ 개선:  싱글톤으로 모델 캐싱                                         │
│        → 첫 호출: 모델 로드 (~2초)                                 │
│        → 이후 호출: 캐시된 모델 사용 (즉시)                        │
│        → 100회 검색 시: ~2초 + α 소요 ✅                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ DB 연결 캐싱                                                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 기존:  매번 lancedb.connect() 호출                                 │
│        → 테이블 메타데이터 재로드                                   │
│                                                                      │
│ 개선:  DB 연결도 캐싱                                               │
│        → 첫 호출: 연결 설정                                         │
│        → 이후 호출: 캐시된 연결 재사용                              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
"""


# ============================================================================
# 🚀 다음 단계
# ============================================================================

"""
1. ✅ db_search_v2.py를 import하는 곳에서 점진적으로 교체
   
   # agents/es_agent.py 예:
   # from src.services.db_search import search_esg_database
   # 👇 변경
   from src.services.db_search_v2 import ESGSearchService
   
   service = ESGSearchService()
   response = service.search_esg_reports(query_text=query)

2. ✅ logging 설정 추가 (main.py)
   
   import logging
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )

3. ✅ API 응답을 Pydantic 모델로 통일 (main.py)
   
   from src.services.db_search_v2 import ESGSearchService
   from fastapi import FastAPI
   
   app = FastAPI()
   service = ESGSearchService()
   
   @app.post("/api/search")
   def api_search(query: str) -> SearchResponse:
       return service.search_esg_reports(query)

4. ✅ 에러 처리 개선
   
   try:
       response = service.search_esg_reports(query)
       if not response.success:
           raise HTTPException(status_code=400, detail=response.message)
   except SearchError as e:
       raise HTTPException(status_code=500, detail=str(e))
"""
