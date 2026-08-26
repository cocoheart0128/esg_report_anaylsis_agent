"""
데이터베이스 및 검색 관련 설정을 중앙 관리합니다.
프로덕션 환경과 개발 환경을 지원합니다.
"""

import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Environment(Enum):
    """실행 환경 구분"""
    DEVELOPMENT = "development"
    DOCKER = "docker"
    CLOUD = "cloud"


@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""
    
    # ========================
    # 경로 설정
    # ========================
    db_path: str
    
    # ========================
    # 테이블 명 (스키마)
    # ========================
    TABLE_CORP_GOV_REPORT = "tb_esg_corp_gov_report"      # 비정형 문서
    TABLE_GRADE_INFO = "tb_esg_grade_info"                # 정형 등급 정보
    
    # ========================
    # 컬럼 명 (일관된 필드명)
    # ========================
    COL_ISU_CD = "isu_cd"                   # 종목코드
    COL_EVAL_YEAR = "eval_year"            # 평가연도
    COL_COM_ABBRV = "com_abbrv"            # 회사명 약칭
    COL_TEXT = "text"                       # 문서 텍스트
    COL_VECTOR = "vector"                   # 임베딩 벡터
    COL_DISTANCE = "_distance"              # 검색 거리 (LanceDB)
    
    # ========================
    # 임베딩 설정
    # ========================
    EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"
    
    # ========================
    # 검색 설정
    # ========================
    SEARCH_LIMIT_DEFAULT = 10               # 기본 검색 결과 개수
    SEARCH_QUERY_TYPE_HYBRID = "hybrid"     # 하이브리드 검색
    
    # ========================
    # FTS (Full-Text Search) 설정
    # ========================
    FTS_INDEX_COLUMN = "text"              # FTS 인덱스 대상 컬럼
    
    @classmethod
    def create_from_env(cls) -> "DatabaseConfig":
        """
        현재 실행 환경을 감지하여 적절한 설정을 반환합니다.
        
        Returns:
            DatabaseConfig: 환경에 맞는 데이터베이스 설정
        """
        env = cls._detect_environment()
        db_path = cls._get_db_path(env)
        
        print(f"🔧 [환경 감지] {env.value} 모드 - DB: {db_path}")
        return cls(db_path=db_path)
    
    @staticmethod
    def _detect_environment() -> Environment:
        """현재 실행 환경 감지"""
        if os.path.exists("/app"):
            return Environment.DOCKER
        elif os.environ.get("STREAMLIT_SERVER_RUNONCMD"):
            return Environment.CLOUD
        else:
            return Environment.DEVELOPMENT
    
    @staticmethod
    def _get_db_path(env: Environment) -> str:
        """환경에 맞는 DB 경로 반환"""
        if env == Environment.CLOUD:
            # Streamlit Cloud: /app에 쓰기 권한 없으므로 /tmp 사용
            if not os.access("/app", os.W_OK):
                return os.path.join(tempfile.gettempdir(), "esg_lancedb")
            return "data/esg_lancedb"
        
        elif env == Environment.DOCKER:
            # Docker: /app 기준
            return "/app/data/esg_lancedb"
        
        else:
            # 로컬 개발: 상대 경로
            return "data/esg_lancedb"


# 🌍 전역 인스턴스 (싱글톤 패턴)
_db_config: Optional[DatabaseConfig] = None


def get_db_config() -> DatabaseConfig:
    """
    데이터베이스 설정 인스턴스를 가져옵니다 (캐싱됨).
    
    Returns:
        DatabaseConfig: 싱글톤 데이터베이스 설정
    """
    global _db_config
    if _db_config is None:
        _db_config = DatabaseConfig.create_from_env()
    return _db_config


def reset_db_config() -> None:
    """설정 캐시를 초기화합니다 (테스트용)"""
    global _db_config
    _db_config = None
