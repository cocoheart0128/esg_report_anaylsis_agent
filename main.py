import lancedb
from src.etl.pipeline import run_etl_pipeline
from src.services.rag_service import ESGRagService
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

def check_data_exists(db_path: str, isu_cd: str, start_yr: str, end_yr: str) -> bool:
    """
    LanceDB에 접속하여 해당 회사코드(isu_cd)와 연도 범위의 데이터가 
    tb_esg_corp_gov_report 테이블에 적재되어 있는지 확인합니다.
    """
    try:
        db = lancedb.connect(db_path)
        tables = db.table_names()
        
        # 테이블 자체가 없으면 데이터도 없음
        if "tb_esg_corp_gov_report" not in tables:
            return False
            
        table = db.open_table("tb_esg_corp_gov_report")
        # table.search().to_pandas().to_csv("debug_tb_esg_corp_gov_report.csv", index=False)  # 디버깅용 CSV 저장
        
        # Flat Schema 기반 SQL 필터 검색
        # (해당 회사코드 & 시작~종료 연도 사이의 데이터가 1건이라도 있는지 확인)
        query_str = f"isu_cd = '{isu_cd}' AND eval_year >= {start_yr} AND eval_year <= {end_yr}"
        result = table.search().where(query_str).limit(5).to_pandas()
        
        # 결과가 비어있지 않으면(False가 아니면) 데이터가 존재하는 것
        return not result.empty

    except Exception as e:
        print(f"⚠️ DB 확인 중 오류 발생 (최초 실행 환경일 수 있음): {e}")
        return False

def main():
    print("🌟 ESG 통합 분석 시스템 (Auto DB Check 지원) 🌟\n")
    
    # 1. 사용자 입력 받기
    isu_cd = input("▶ 회사코드(종목코드 6자리)를 입력하세요 (예: 282330): ").strip()
    start_yr = input("▶ 시작 연도를 입력하세요 (예: 2024): ").strip()
    end_yr = input("▶ 종료 연도를 입력하세요 (예: 2026): ").strip()
    query = input("▶ 질문을 입력하세요: ").strip()
    
    if not query:
        query = "이사회 구성과 관련된 주요 내용을 요약해 줘."

    db_path = "/app/data/esg_lancedb"
    llm_provider = "gemini"  # 사용하시는 LLM 이름
    
    # 2. DB 데이터 존재 여부 자동 판단
    print(f"\n🔍 DB 검사 중... [종목코드: {isu_cd} | {start_yr}~{end_yr}년]")
    has_data = check_data_exists(db_path, isu_cd, start_yr, end_yr)

    # 3. 데이터가 없으면 ETL 실행
    if not has_data:
        print("⚠️ DB에 데이터가 없습니다. [ETL 파이프라인]을 가동하여 데이터를 수집합니다.")
        run_etl_pipeline(start_yr=start_yr, end_yr=end_yr, isu_cd=isu_cd)
        print("✅ 데이터 적재 완료!\n")
    else:
        print("✅ DB에 데이터가 이미 존재합니다. ETL을 건너뛰고 바로 [RAG 서비스]를 실행합니다.\n")

    # 4. RAG 서비스 실행
    print("[🧠 STEP 2] AI 애널리스트 분석 시작...")
    try:
        rag_service = ESGRagService(db_path=db_path)
        
        # RAG 검색 시 가장 최신 연도(end_yr)를 타겟으로 하거나 
        # year=None 으로 주어 수집된 전 기간에서 검색하게 할 수 있습니다.
        answer = rag_service.analyze_esg(
            query=query, 
            llm_provider=llm_provider,
            isu_cd=isu_cd, 
            year=None # 시작~종료 연도 범위 전체에서 유사도를 찾으려면 None 입력
        )
        
        print("\n" + "="*50)
        print("🤖 [AI 애널리스트 답변]")
        print("="*50)
        print(answer)
        print("="*50)
        
    except Exception as e:
        print(f"❌ RAG 실행 중 오류 발생: {e}")

if __name__ == "__main__":
    main()