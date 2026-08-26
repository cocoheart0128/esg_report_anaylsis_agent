"""
검색 및 데이터베이스 관련 데이터 타입을 정의합니다.
Pydantic을 사용하여 타입 안전성과 검증을 보장합니다.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """검색 결과 항목"""
    
    company: str = Field(..., description="회사 약칭", alias="com_abbrv")
    year: str = Field(..., description="평가 연도", alias="eval_year")
    text: str = Field(..., description="문서 텍스트")
    score: float = Field(..., description="검색 유사도 점수 (0~1, 높을수록 유사)")
    
    class Config:
        populate_by_name = True  # alias 이름으로도 접근 가능


class SearchResponse(BaseModel):
    """검색 응답"""
    
    success: bool = Field(..., description="검색 성공 여부")
    count: int = Field(..., description="반환된 결과 개수")
    results: List[SearchResult] = Field(default_factory=list, description="검색 결과 목록")
    message: Optional[str] = Field(None, description="안내 메시지 또는 에러 메시지")
    search_mode: str = Field("vector", description="사용된 검색 모드 (vector/hybrid)")


class ESGGrade(BaseModel):
    """ESG 등급 정보"""
    
    class AgencyGrade(BaseModel):
        year: Optional[str] = "-"
        grade: Optional[str] = "-"
    
    com_abbrv: str = Field(..., description="회사 약칭")
    isu_cd: str = Field(..., description="종목코드")
    target_year: str = Field(..., description="대상 평가 연도")
    
    # 한국ESG기준원 (KCGS)
    kcgs: Dict[str, str] = Field(
        default_factory=lambda: {"year": "-", "esg": "-", "env": "-", "soc": "-", "gov": "-"},
        description="한국ESG기준원 등급 (E/S/G 세분화)"
    )
    
    # 기타 평가기관
    msci: Dict[str, str] = Field(default_factory=lambda: {"year": "-", "esg": "-"})
    sp: Dict[str, str] = Field(default_factory=lambda: {"year": "-", "esg": "-"})
    kesg: Dict[str, str] = Field(default_factory=lambda: {"year": "-", "esg": "-"})
    sv: Dict[str, str] = Field(default_factory=lambda: {"year": "-", "esg": "-"})
    
    # 공시 보고서 링크
    reports: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="공식 공시 보고서 링크"
    )


class GradeResponse(BaseModel):
    """ESG 등급 응답"""
    
    success: bool = Field(..., description="조회 성공 여부")
    data: Optional[ESGGrade] = Field(None, description="ESG 등급 데이터")
    message: Optional[str] = Field(None, description="안내 메시지 또는 에러 메시지")


class YearsResponse(BaseModel):
    """사용 가능한 연도 목록 응답"""
    
    success: bool = Field(..., description="조회 성공 여부")
    years: List[str] = Field(default_factory=list, description="사용 가능한 연도 목록 (최신순)")
    message: Optional[str] = Field(None, description="안내 메시지 또는 에러 메시지")


class DBError(Exception):
    """데이터베이스 관련 에러의 기본 클래스"""
    pass


class FTSIndexMissingError(DBError):
    """FTS 인덱스 부재 에러"""
    pass


class TableNotFoundError(DBError):
    """테이블 미존재 에러"""
    pass


class SearchError(DBError):
    """검색 실행 중 발생한 에러"""
    pass


class EmbeddingError(DBError):
    """임베딩 생성 중 발생한 에러"""
    pass
