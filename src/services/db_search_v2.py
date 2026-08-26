"""
LanceDB를 이용한 ESG 데이터 검색 서비스

기능:
- 하이브리드 검색 (벡터 + 전문검색)
- 벡터 전용 검색 (FTS 인덱스 미존재시 자동 폴백)
- ESG 등급 조회
- 사용 가능 연도 조회
- 구조화된 에러 처리 및 로깅
"""

import logging
from typing import List, Optional
from langchain_huggingface import HuggingFaceEmbeddings

import lancedb

from src.config.database_config import get_db_config, DatabaseConfig
from src.schemas.search_schemas import (
    SearchResult,
    SearchResponse,
    ESGGrade,
    GradeResponse,
    YearsResponse,
    FTSIndexMissingError,
    TableNotFoundError,
    SearchError,
    EmbeddingError,
)

logger = logging.getLogger(__name__)


class ESGSearchService:
    """
    ESG 데이터 검색 서비스
    
    하이브리드 검색, 벡터 검색, 등급 조회 등을 담당합니다.
    싱글톤 패턴으로 임베딩 모델을 캐싱합니다.
    """
    
    _instance = None
    _embeddings = None
    
    def __new__(cls):
        """싱글톤 패턴: 인스턴스는 한 번만 생성"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """생성자 (싱글톤이므로 한 번만 실행)"""
        if self._initialized:
            return
        
        self.config = get_db_config()
        self._db = None
        self._initialized = True
        
        logger.info(f"✅ ESGSearchService 초기화 완료 (DB: {self.config.db_path})")
    
    # ============================================================================
    # 내부 헬퍼 메서드
    # ============================================================================
    
    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """임베딩 모델을 반환합니다 (캐싱됨)"""
        if ESGSearchService._embeddings is None:
            try:
                logger.info(f"📥 임베딩 모델 로딩: {self.config.EMBEDDING_MODEL}")
                ESGSearchService._embeddings = HuggingFaceEmbeddings(
                    model_name=self.config.EMBEDDING_MODEL
                )
                logger.info("✅ 임베딩 모델 로딩 완료")
            except Exception as e:
                logger.error(f"❌ 임베딩 모델 로딩 실패: {e}")
                raise EmbeddingError(f"임베딩 모델 로딩 실패: {e}") from e
        
        return ESGSearchService._embeddings
    
    @property
    def db(self) -> lancedb.DBConnection:
        """LanceDB 연결을 반환합니다 (캐싱됨)"""
        if self._db is None:
            try:
                self._db = lancedb.connect(self.config.db_path)
                logger.info(f"✅ LanceDB 연결 성공: {self.config.db_path}")
            except Exception as e:
                logger.error(f"❌ LanceDB 연결 실패: {e}")
                raise SearchError(f"DB 연결 실패: {e}") from e
        
        return self._db
    
    def _build_filter_condition(
        self, 
        isu_cd: Optional[str] = None, 
        year: Optional[str] = None
    ) -> Optional[str]:
        """
        필터 조건 문자열을 생성합니다.
        
        Args:
            isu_cd: 종목코드 (예: "000913")
            year: 평가 연도 (예: "2024")
        
        Returns:
            필터 조건 문자열 또는 None
        """
        filters = []
        
        if isu_cd:
            filters.append(f"{self.config.COL_ISU_CD} = '{isu_cd.strip()}'")
        
        if year:
            # year가 숫자인지 문자인지 자동 판단
            year_clean = str(year).strip()
            try:
                year_int = int(year_clean)
                filters.append(f"{self.config.COL_EVAL_YEAR} = {year_int}")
            except ValueError:
                filters.append(f"{self.config.COL_EVAL_YEAR} = '{year_clean}'")
        
        return " AND ".join(filters) if filters else None
    
    def _parse_search_result(self, record: dict) -> SearchResult:
        """
        DB 레코드를 SearchResult로 변환합니다.
        
        Args:
            record: LanceDB에서 반환한 레코드 딕셔너리
        
        Returns:
            SearchResult 객체
        """
        return SearchResult(
            com_abbrv=record.get(self.config.COL_COM_ABBRV, "알수없음"),
            eval_year=str(record.get(self.config.COL_EVAL_YEAR, "알수없음")),
            text=record.get(self.config.COL_TEXT, ""),
            score=float(record.get(self.config.COL_DISTANCE, 0.0))
        )
    
    # ============================================================================
    # 주요 공개 메서드
    # ============================================================================
    
    def search_esg_reports(
        self,
        query_text: str,
        isu_cd: Optional[str] = None,
        year: Optional[str] = None,
        limit: int = None
    ) -> SearchResponse:
        """
        ESG 보고서를 검색합니다.
        
        하이브리드 검색(벡터 + FTS)을 시도하고, FTS 인덱스가 없으면 벡터 검색으로 폴백합니다.
        
        Args:
            query_text: 검색 쿼리 (예: "환경 정책")
            isu_cd: 종목코드 필터 (선택사항)
            year: 평가 연도 필터 (선택사항)
            limit: 반환할 최대 결과 개수 (기본값: 10)
        
        Returns:
            SearchResponse 객체 (성공 여부, 결과, 사용된 검색 모드 포함)
        
        Example:
            response = service.search_esg_reports(
                query_text="탄소중립 목표",
                isu_cd="000913",
                year="2024"
            )
            
            if response.success:
                for result in response.results:
                    print(f"{result.company}: {result.score:.2f}")
            else:
                logger.error(response.message)
        """
        limit = limit or self.config.SEARCH_LIMIT_DEFAULT
        search_mode = "unknown"
        
        try:
            # 1. 임베딩 생성
            logger.info(f"🔍 쿼리 임베딩 생성 중: {query_text[:50]}...")
            query_vector = self.embeddings.embed_query(query_text)
            
            # 2. 테이블 열기
            table = self.db.open_table(self.config.TABLE_CORP_GOV_REPORT)
            
            # 3. 필터 조건 생성
            filter_condition = self._build_filter_condition(isu_cd, year)
            
            # 4. 하이브리드 검색 시도
            try:
                logger.debug("🚀 하이브리드 검색 시도 (벡터 + FTS)...")
                search_req = (
                    table.search(query_type=self.config.SEARCH_QUERY_TYPE_HYBRID)
                    .vector(query_vector)
                    .text(query_text)
                    .limit(limit)
                )
                
                if filter_condition:
                    search_req = search_req.where(filter_condition, prefilter=True)
                
                results = search_req.to_list()
                search_mode = "hybrid"
                logger.info(f"✅ 하이브리드 검색 성공 ({len(results)}개 결과)")
            
            except ValueError as e:
                # FTS 인덱스 미존재 -> 벡터 전용 검색으로 폴백
                if "INVERTED index" in str(e):
                    logger.warning("⚠️ FTS 인덱스 미존재 → 벡터 검색으로 폴백")
                    
                    search_req = table.search(query_vector).limit(limit)
                    
                    if filter_condition:
                        search_req = search_req.where(filter_condition, prefilter=True)
                    
                    results = search_req.to_list()
                    search_mode = "vector"
                    logger.info(f"✅ 벡터 검색 성공 ({len(results)}개 결과)")
                else:
                    raise  # 다른 종류의 ValueError는 재발생
            
            # 5. 결과 파싱
            search_results = [self._parse_search_result(r) for r in results]
            
            return SearchResponse(
                success=True,
                count=len(search_results),
                results=search_results,
                search_mode=search_mode,
                message=f"{search_mode} 검색으로 {len(search_results)}개의 결과를 찾았습니다."
            )
        
        except SearchError as e:
            logger.error(f"❌ 검색 에러: {e}")
            return SearchResponse(
                success=False,
                count=0,
                results=[],
                search_mode=search_mode,
                message=f"검색 실패: {str(e)}"
            )
        except Exception as e:
            logger.error(f"❌ 예상치 못한 에러: {e}", exc_info=True)
            return SearchResponse(
                success=False,
                count=0,
                results=[],
                search_mode=search_mode,
                message=f"검색 중 오류 발생: {str(e)}"
            )
    
    def get_esg_grade(
        self,
        isu_cd: str,
        year: Optional[str] = None
    ) -> GradeResponse:
        """
        특정 회사의 ESG 등급 정보를 조회합니다.
        
        Args:
            isu_cd: 종목코드 (예: "000913")
            year: 평가 연도 (선택사항)
        
        Returns:
            GradeResponse 객체 (성공 여부, ESG 등급 데이터 포함)
        
        Example:
            response = service.get_esg_grade(isu_cd="000913", year="2024")
            
            if response.success and response.data:
                print(f"KCGS: {response.data.kcgs.get('esg', '-')}")
                print(f"MSCI: {response.data.msci.get('esg', '-')}")
        """
        try:
            # 1. 테이블 열기
            grade_table = self.db.open_table(self.config.TABLE_GRADE_INFO)
            
            # 2. 필터 조건 생성
            filter_condition = self._build_filter_condition(isu_cd=isu_cd, year=year)
            
            # 3. 데이터 조회
            logger.debug(f"🔍 ESG 등급 조회: {isu_cd} (연도: {year or 'all'})")
            df = grade_table.search().where(filter_condition).to_pandas()
            
            if df.empty:
                msg = f"등급 정보를 찾을 수 없습니다: isu_cd={isu_cd}"
                logger.warning(f"⚠️ {msg}")
                return GradeResponse(success=False, message=msg)
            
            # 4. 결과 파싱
            record = df.iloc[0].to_dict()
            
            grade_data = ESGGrade(
                com_abbrv=record.get(self.config.COL_COM_ABBRV, "알수없음"),
                isu_cd=record.get(self.config.COL_ISU_CD, "-"),
                target_year=str(record.get(self.config.COL_EVAL_YEAR, "-")),
                kcgs={
                    "year": str(record.get("kcgs_yy", "-")),
                    "esg": str(record.get("kcgs_esg", "-")),
                    "env": str(record.get("kcgs_env", "-")),
                    "soc": str(record.get("kcgs_soc", "-")),
                    "gov": str(record.get("kcgs_gov", "-"))
                },
                msci={
                    "year": str(record.get("msci_yy", "-")),
                    "esg": str(record.get("msci_esg", "-"))
                },
                sp={
                    "year": str(record.get("sp_yy", "-")),
                    "esg": str(record.get("sp_esg", "-"))
                },
                kesg={
                    "year": str(record.get("kesg_yy", "-")),
                    "esg": str(record.get("kesg_esg", "-"))
                },
                sv={
                    "year": str(record.get("sv_yy", "-")),
                    "esg": str(record.get("sv_esg", "-"))
                },
                reports={
                    "sustainable_report": {
                        "acpt_no": record.get("acpt_no1", "-"),
                        "title": "지속가능경영보고서",
                        "url": self._make_viewer_url(record.get("acpt_no1"))
                    },
                    "governance_report": {
                        "acpt_no": record.get("acpt_no2", "-"),
                        "title": "기업지배구조보고서",
                        "url": self._make_viewer_url(record.get("acpt_no2"))
                    }
                }
            )
            
            logger.info(f"✅ ESG 등급 조회 성공: {grade_data.com_abbrv}")
            return GradeResponse(success=True, data=grade_data)
        
        except Exception as e:
            logger.error(f"❌ ESG 등급 조회 실패: {e}", exc_info=True)
            return GradeResponse(
                success=False,
                message=f"등급 조회 중 오류 발생: {str(e)}"
            )
    
    def get_available_years(self, isu_cd: str) -> YearsResponse:
        """
        특정 회사의 사용 가능한 모든 평가 연도를 조회합니다.
        
        Args:
            isu_cd: 종목코드 (예: "000913")
        
        Returns:
            YearsResponse 객체 (성공 여부, 연도 목록 포함)
        
        Example:
            response = service.get_available_years(isu_cd="000913")
            
            if response.success:
                print(f"사용 가능한 연도: {', '.join(response.years)}")
        """
        try:
            # 1. 테이블 열기
            grade_table = self.db.open_table(self.config.TABLE_GRADE_INFO)
            
            # 2. 전체 데이터를 판다스로 조회 (가장 안정적)
            logger.debug(f"🔍 사용 가능한 연도 조회: {isu_cd}")
            df = grade_table.to_pandas()
            
            # 3. 종목코드로 필터링
            filtered_df = df[
                df[self.config.COL_ISU_CD].astype(str) == str(isu_cd).strip()
            ]
            
            if filtered_df.empty:
                msg = f"해당 종목의 데이터가 없습니다: {isu_cd}"
                logger.warning(f"⚠️ {msg}")
                return YearsResponse(success=False, message=msg)
            
            # 4. 연도 추출 및 정렬 (최신순)
            years = sorted(
                filtered_df[self.config.COL_EVAL_YEAR]
                .dropna()
                .unique()
                .tolist(),
                reverse=True
            )
            
            years_str = [
                str(int(y)) if isinstance(y, float) else str(y) 
                for y in years
            ]
            
            logger.info(f"✅ 사용 가능한 연도: {years_str}")
            return YearsResponse(
                success=True,
                years=years_str,
                message=f"{len(years_str)}개의 평가 연도를 찾았습니다."
            )
        
        except Exception as e:
            logger.error(f"❌ 연도 조회 실패: {e}", exc_info=True)
            return YearsResponse(
                success=False,
                message=f"연도 조회 중 오류 발생: {str(e)}"
            )
    
    # ============================================================================
    # 유틸리티 메서드
    # ============================================================================
    
    @staticmethod
    def _make_viewer_url(acpt_no: Optional[str]) -> Optional[str]:
        """
        KIND 공시 뷰어 URL을 생성합니다.
        
        Args:
            acpt_no: 접수번호
        
        Returns:
            KIND 뷰어 URL 또는 None
        """
        if not acpt_no or acpt_no in ("nan", "-"):
            return None
        
        return f"https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={acpt_no}"


# ============================================================================
# 하위호환성을 위한 함수 래퍼
# ============================================================================

def search_esg_database(
    query_text: str,
    isu_cd: Optional[str] = None,
    year: Optional[str] = None,
    db_path: Optional[str] = None
) -> List[dict]:
    """
    [레거시] ESG 데이터베이스를 검색합니다.
    
    새로운 코드에서는 ESGSearchService를 직접 사용하는 것을 권장합니다.
    
    Args:
        query_text: 검색 쿼리
        isu_cd: 종목코드 필터
        year: 연도 필터
        db_path: DB 경로 (무시됨, 자동 감지)
    
    Returns:
        검색 결과 딕셔너리 리스트
    """
    service = ESGSearchService()
    response = service.search_esg_reports(query_text, isu_cd, year)
    
    return [r.dict(by_alias=True) for r in response.results]


def get_esg_grade_from_lancedb(
    isu_cd: str,
    year: Optional[str] = None,
    db_path: Optional[str] = None
) -> Optional[dict]:
    """
    [레거시] ESG 등급 정보를 조회합니다.
    
    새로운 코드에서는 ESGSearchService를 직접 사용하는 것을 권장합니다.
    
    Args:
        isu_cd: 종목코드
        year: 평가 연도
        db_path: DB 경로 (무시됨, 자동 감지)
    
    Returns:
        ESG 등급 딕셔너리 또는 None
    """
    service = ESGSearchService()
    response = service.get_esg_grade(isu_cd, year)
    
    return response.data.dict() if response.data else None


def get_company_data_years(
    db_path: Optional[str] = None,
    isu_cd: Optional[str] = None
) -> List[str]:
    """
    [레거시] 회사의 사용 가능한 연도를 조회합니다.
    
    새로운 코드에서는 ESGSearchService를 직접 사용하는 것을 권장합니다.
    
    Args:
        db_path: DB 경로 (무시됨, 자동 감지)
        isu_cd: 종목코드
    
    Returns:
        연도 문자열 리스트
    """
    if not isu_cd:
        return []
    
    service = ESGSearchService()
    response = service.get_available_years(isu_cd)
    
    return response.years if response.success else []
