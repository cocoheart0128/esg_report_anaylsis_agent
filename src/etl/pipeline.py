import concurrent.futures
import pandas as pd
import lancedb
from src.etl.extractor import ESGExtractor
from src.etl.transformer import ESGTransformer
from src.etl.loader import ESGLoader

def run_etl_pipeline(start_yr="2024", end_yr="2026", isu_cd="282330"):
    print("=== 🚀 1. ESG ETL 파이프라인 시작 ===")
    
    extractor = ESGExtractor()
    transformer = ESGTransformer()
    # 도커 내부에서는 /app/data/esg_lancedb 경로에 저장됩니다.
    loader = ESGLoader(db_path="/app/data/esg_lancedb")
    
    # 1. ESG 등급 데이터 수집
    print("=== 📊 대상 기업 원본 데이터 수집 중 ===")
    df = extractor.fetch_full_esg_data(start_yr=start_yr, end_yr=end_yr, isu_cd=isu_cd)
    print(df.head(3))  # 수집된 데이터 일부 확인
    
    if df.empty:
        print("❌ 수집된 데이터가 없습니다.")
        return
    print(f"✅ 원본 데이터 {len(df)}건 수집 완료")

    # 2. DataFrame 원본 적재 (tb_esg_grade_info 테이블)
    loader.load_structured_data(df=df, table_name="tb_esg_grade_info",pk=["eval_year", "isu_cd"])

    # 3. 문서 변환 처리 (Extract & Transform)
    print(f"\n=== ✂️ {len(df)}건의 문서 파싱 및 분할 시작 ===")
    
    # URL 정보(acpt_no2_doc_json)가 존재하는 유효한 행(Row)만 필터링
    valid_rows = [
        row for _, row in df.iterrows() 
        if pd.notna(row.get('acpt_no2_doc_json')) and str(row.get('acpt_no2_doc_json')).strip() != ""
    ]
    all_chunks = []
    
    # transformer.process_dataframe_row 에 row를 통째로 던져 병렬 처리
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(transformer.process_dataframe_row, row) for row in valid_rows]
        
        for future in concurrent.futures.as_completed(futures):
            chunks = future.result()
            if chunks:
                all_chunks.extend(chunks)
                
    # 4. 문서 청크 DB 적재 (tb_esg_corp_gov_report 테이블)
    if all_chunks:
        loader.load_vector_data(
            documents=all_chunks, 
            table_name="tb_esg_corp_gov_report",
            doc_id_key="doc_id"  # 🌟 수정됨: acptno 대신 스키마에 맞춰 'doc_id'로 전달
        )
    else:
        print("⚠️ 적재할 텍스트 청크가 없습니다 (해당 기업의 문서가 없거나 파싱 실패).")
        
    print("=== ✨ ETL 파이프라인 테스트 종료 ===\n")


def check_lancedb_data():
    db_path = "/app/data/esg_lancedb"
    print(f"📂 DB 경로: {db_path}")
    db = lancedb.connect(db_path)

    # 생성된 테이블 목록 확인
    tables = db.table_names()
    print(f"🗂️ 현재 생성된 테이블 목록: {tables}")
    
    if "tb_esg_grade_info" in tables:
        print("\n=== 📊 [Table 1] tb_esg_grade_info (ESG 등급 데이터) ===")
        tbl_grade = db.open_table("tb_esg_grade_info")
        df_grade = tbl_grade.to_pandas()
        print(f"총 데이터 수: {len(df_grade)}건")
        print(df_grade.head(3))
        
    if "tb_esg_corp_gov_report" in tables:
        print("\n=== 📝 [Table 2] tb_esg_corp_gov_report (Flat 스키마 벡터 데이터) ===")
        tbl_report = db.open_table("tb_esg_corp_gov_report")

        
        total_chunks = tbl_report.count_rows()
        print(f"총 텍스트 청크 수: {total_chunks}건")
        
        df_report = tbl_report.search().limit(10).to_pandas()
        print(df_report.head(3))
        
        for idx, row in df_report.iterrows():
            print(f"\n[청크 {idx+1}]")
            
            # 🌟 핵심 변경점: Flat Schema이므로 metadata 객체가 없습니다! 
            # 일반 DataFrame 컬럼처럼 최상위 row에서 바로 꺼냅니다.
            print(f"- 청크 ID: {row.get('chunk_id')}")
            print(f"- 원본 문서 ID: {row.get('doc_id')}")
            print(f"- 기업명: {row.get('com_abbrv')} ({row.get('eval_year')}년)")
            print(f"- 목차명: {row.get('toc_name')}")
            print(f"- 청크 인덱스: {row.get('chunk_index')}")
            
            content = row.get('text', '내용 없음')
            print(f"- 본문 내용: {content[:100].replace(chr(10), ' ')}...")
            
            vector = row.get('vector')
            if vector is not None:
                print(f"- 벡터 임베딩 차원수: {len(vector)} 차원")


# if __name__ == "__main__":

#     # db = lancedb.connect("/app/data/esg_lancedb")
#     # # 테이블이 존재하는지 확인 후 삭제
#     # if "tb_esg_corp_gov_report" in db.table_names() or "tb_esg_grade_info" in db.table_names():
#     #     if "tb_esg_corp_gov_report" in db.table_names():
#     #         db.drop_table("tb_esg_corp_gov_report")
#     #         print("🗑️ 테이블이 삭제되었습니다.")
#     #     if "tb_esg_grade_info" in db.table_names():
#     #         db.drop_table("tb_esg_grade_info")
#     #         print("🗑️ 테이블이 삭제되었습니다.")

#     run_etl_pipeline()