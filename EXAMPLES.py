"""
ESGSearchService 사용 예제 모음
프로덕션 환경에서의 실제 사용 사례를 보여줍니다.
"""

import logging
from typing import List, Dict, Any
from src.services.db_search_v2 import ESGSearchService
from src.schemas.search_schemas import SearchResponse, GradeResponse


# ============================================================================
# 로깅 설정 (프로덕션 환경 권장)
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# 예제 1: 기본 검색
# ============================================================================

def example_basic_search():
    """
    기본 검색 예제
    """
    print("\n" + "="*70)
    print("예제 1: 기본 검색")
    print("="*70)
    
    service = ESGSearchService()
    
    # 쿼리 검색
    response = service.search_esg_reports(
        query_text="탄소중립 목표"
    )
    
    print(f"검색 성공: {response.success}")
    print(f"결과 개수: {response.count}")
    print(f"검색 모드: {response.search_mode}")
    print(f"메시지: {response.message}")
    
    # 결과 출력
    for i, result in enumerate(response.results, 1):
        print(f"\n[결과 {i}]")
        print(f"  회사: {result.company}")
        print(f"  연도: {result.year}")
        print(f"  점수: {result.score:.4f}")
        print(f"  텍스트: {result.text[:100]}...")


# ============================================================================
# 예제 2: 필터와 함께 검색
# ============================================================================

def example_filtered_search():
    """
    회사 코드와 연도로 필터링하여 검색
    """
    print("\n" + "="*70)
    print("예제 2: 필터와 함께 검색")
    print("="*70)
    
    service = ESGSearchService()
    
    # 특정 회사, 특정 연도로 검색
    response = service.search_esg_reports(
        query_text="환경 정책",
        isu_cd="000913",      # 삼성전자
        year="2024",
        limit=5
    )
    
    if response.success:
        print(f"✅ {len(response.results)}개의 결과를 찾았습니다")
        
        for result in response.results:
            print(f"\n  [{result.company}] {result.year}")
            print(f"    유사도: {result.score:.2%}")
            print(f"    내용: {result.text[:80]}...")
    else:
        print(f"❌ 검색 실패: {response.message}")


# ============================================================================
# 예제 3: ESG 등급 조회
# ============================================================================

def example_get_grade():
    """
    특정 회사의 ESG 등급 정보 조회
    """
    print("\n" + "="*70)
    print("예제 3: ESG 등급 조회")
    print("="*70)
    
    service = ESGSearchService()
    
    # 등급 조회
    response = service.get_esg_grade(
        isu_cd="000913",
        year="2024"
    )
    
    if response.success and response.data:
        grade = response.data
        
        print(f"\n회사: {grade.com_abbrv} ({grade.isu_cd})")
        print(f"평가 연도: {grade.target_year}")
        print("\n📊 ESG 등급:")
        
        # KCGS (한국ESG기준원)
        print(f"\n  한국ESG기준원 (KCGS) [{grade.kcgs.get('year', '-')}]")
        print(f"    전체: {grade.kcgs.get('esg', '-')}")
        print(f"    환경(E): {grade.kcgs.get('env', '-')}")
        print(f"    사회(S): {grade.kcgs.get('soc', '-')}")
        print(f"    지배구조(G): {grade.kcgs.get('gov', '-')}")
        
        # 기타 평가기관
        print(f"\n  기타 평가기관:")
        print(f"    MSCI: {grade.msci.get('esg', '-')} [{grade.msci.get('year', '-')}]")
        print(f"    S&P: {grade.sp.get('esg', '-')} [{grade.sp.get('year', '-')}]")
        print(f"    KESG: {grade.kesg.get('esg', '-')} [{grade.kesg.get('year', '-')}]")
        print(f"    서스틴베스트: {grade.sv.get('esg', '-')} [{grade.sv.get('year', '-')}]")
        
        # 공시 보고서 링크
        if grade.reports:
            print(f"\n📄 공시 보고서:")
            for report_type, report_info in grade.reports.items():
                if report_info.get('url'):
                    print(f"    [{report_info.get('title')}]")
                    print(f"      접수번호: {report_info.get('acpt_no')}")
                    print(f"      URL: {report_info.get('url')}")
    else:
        print(f"❌ 등급 조회 실패: {response.message}")


# ============================================================================
# 예제 4: 사용 가능한 연도 조회
# ============================================================================

def example_get_years():
    """
    특정 회사의 사용 가능한 평가 연도 조회
    """
    print("\n" + "="*70)
    print("예제 4: 사용 가능한 연도 조회")
    print("="*70)
    
    service = ESGSearchService()
    
    # 연도 조회
    response = service.get_available_years(isu_cd="000913")
    
    if response.success:
        print(f"\n삼성전자 (000913)의 사용 가능한 연도:")
        for i, year in enumerate(response.years, 1):
            print(f"  {i}. {year}년")
    else:
        print(f"❌ 연도 조회 실패: {response.message}")


# ============================================================================
# 예제 5: 대량 검색 (배치 처리)
# ============================================================================

def example_batch_search():
    """
    여러 쿼리를 한 번에 검색 (배치 처리)
    """
    print("\n" + "="*70)
    print("예제 5: 대량 검색 (배치 처리)")
    print("="*70)
    
    service = ESGSearchService()
    
    queries = [
        "탄소 감축",
        "재생 에너지",
        "사회적 책임",
        "지배구조 개선"
    ]
    
    results_summary = {}
    
    for query in queries:
        response = service.search_esg_reports(query_text=query, limit=3)
        
        results_summary[query] = {
            "success": response.success,
            "count": response.count,
            "mode": response.search_mode,
            "results": [
                {
                    "company": r.company,
                    "score": r.score
                }
                for r in response.results
            ]
        }
        
        print(f"\n[{query}]")
        if response.success:
            print(f"  결과: {response.count}개")
            for result in response.results[:3]:
                print(f"    - {result.company}: {result.score:.2%}")
        else:
            print(f"  ❌ {response.message}")
    
    return results_summary


# ============================================================================
# 예제 6: 에러 처리
# ============================================================================

def example_error_handling():
    """
    여러 상황에서의 에러 처리
    """
    print("\n" + "="*70)
    print("예제 6: 에러 처리")
    print("="*70)
    
    service = ESGSearchService()
    
    # Case 1: 빈 쿼리
    print("\n[Case 1] 빈 쿼리 처리")
    response = service.search_esg_reports(query_text="")
    if response.success:
        print(f"  ✓ 결과: {response.count}개")
    else:
        print(f"  ℹ️ {response.message}")
    
    # Case 2: 존재하지 않는 회사
    print("\n[Case 2] 존재하지 않는 회사 필터")
    response = service.search_esg_reports(
        query_text="환경",
        isu_cd="999999"  # 존재하지 않는 코드
    )
    if response.success:
        print(f"  ✓ 결과: {response.count}개")
    else:
        print(f"  ℹ️ {response.message}")
    
    # Case 3: 존재하지 않는 등급 정보
    print("\n[Case 3] 존재하지 않는 등급 정보")
    response = service.get_esg_grade(isu_cd="999999")
    if response.success:
        print(f"  ✓ 등급: {response.data}")
    else:
        print(f"  ℹ️ {response.message}")


# ============================================================================
# 예제 7: 응답 JSON 직렬화
# ============================================================================

def example_json_serialization():
    """
    응답을 JSON으로 직렬화 (API 응답용)
    """
    print("\n" + "="*70)
    print("예제 7: 응답 JSON 직렬화")
    print("="*70)
    
    service = ESGSearchService()
    
    # 검색 응답
    response = service.search_esg_reports(
        query_text="환경",
        limit=2
    )
    
    # dict로 변환 (by_alias=True: 필드명을 alias로 변환)
    response_dict = response.model_dump(by_alias=True)
    
    print("\n[검색 응답 - dict 형식]")
    print(f"Success: {response_dict['success']}")
    print(f"Count: {response_dict['count']}")
    print(f"Mode: {response_dict['search_mode']}")
    
    # JSON 문자열로 변환
    response_json = response.model_dump_json(
        indent=2,
        by_alias=True,
        exclude_none=True  # None 값은 제외
    )
    
    print("\n[JSON 형식 (축약)]")
    print(response_json[:500] + "...")


# ============================================================================
# 예제 8: FastAPI 통합
# ============================================================================

def example_fastapi_integration():
    """
    FastAPI 웹 프레임워크와의 통합 예제
    (실제 코드는 main.py 등에 구현)
    """
    code = '''
from fastapi import FastAPI, HTTPException, Query
from src.services.db_search_v2 import ESGSearchService
from src.schemas.search_schemas import SearchResponse, GradeResponse, YearsResponse

app = FastAPI(title="ESG 검색 API")
service = ESGSearchService()


@app.get("/health")
def health_check():
    """헬스 체크"""
    return {"status": "ok"}


@app.post("/api/v1/search", response_model=SearchResponse)
def api_search(
    query: str = Query(..., description="검색 쿼리"),
    isu_cd: str = Query(None, description="종목코드"),
    year: str = Query(None, description="평가 연도"),
    limit: int = Query(10, description="결과 개수")
):
    """ESG 보고서 검색"""
    return service.search_esg_reports(
        query_text=query,
        isu_cd=isu_cd,
        year=year,
        limit=limit
    )


@app.get("/api/v1/grade/{isu_cd}", response_model=GradeResponse)
def api_get_grade(
    isu_cd: str = Query(..., description="종목코드"),
    year: str = Query(None, description="평가 연도")
):
    """ESG 등급 조회"""
    return service.get_esg_grade(isu_cd, year)


@app.get("/api/v1/years/{isu_cd}", response_model=YearsResponse)
def api_get_years(isu_cd: str = Query(..., description="종목코드")):
    """사용 가능한 연도 조회"""
    return service.get_available_years(isu_cd)


# 실행: uvicorn main:app --reload
'''
    
    print("\n" + "="*70)
    print("예제 8: FastAPI 통합")
    print("="*70)
    print(code)


# ============================================================================
# 메인 실행
# ============================================================================

if __name__ == "__main__":
    print("\n🚀 ESGSearchService 사용 예제\n")
    
    try:
        # 예제 실행
        example_basic_search()
        example_filtered_search()
        example_get_grade()
        example_get_years()
        example_batch_search()
        example_error_handling()
        example_json_serialization()
        example_fastapi_integration()
        
        print("\n" + "="*70)
        print("✅ 모든 예제 실행 완료!")
        print("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"예제 실행 중 오류: {e}", exc_info=True)
