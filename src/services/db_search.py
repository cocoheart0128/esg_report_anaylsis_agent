# src/services/db_search.py
import lancedb
from langchain_huggingface import HuggingFaceEmbeddings

def search_esg_database(query_text: str, isu_cd: str = None, year: str = None, db_path: str = "/app/data/esg_lancedb"):
    """DB 연결, 임베딩, 하이브리드 검색을 전담하는 유틸 함수"""
    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
    db = lancedb.connect(db_path)
    table = db.open_table("tb_esg_corp_gov_report")
    
    filters = []
    if isu_cd: filters.append(f"isu_cd = '{isu_cd}'")
    if year: filters.append(f"eval_year = {year}")
    filter_str = " AND ".join(filters) if filters else None

    query_vector = embeddings.embed_query(query_text)

    search_req = table.search(query_type="hybrid").vector(query_vector).text(query_text).limit(10)
    if filter_str:
        search_req = search_req.where(filter_str, prefilter=True)
        
    results = search_req.to_list()
    
    docs_data = []
    for res in results:
        docs_data.append({
            "com_abbrv": res.get("com_abbrv", "알수없음"),
            "eval_year": res.get("eval_year", "알수없음"),
            "text": res.get("text", ""),
            "score": res.get("_distance", res.get("score", res.get("_score", 0.0)))
        })
        
    return docs_data

# KIND 공시 뷰어 링크 생성 함수 (접수번호가 있으면 링크 생성, 없으면 None)
def make_viewer_url(acptno):
    if acptno and acptno != "nan" and acptno != "-":
        return f"https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={acptno}"
    return None

# 🌟 [추가] tb_esg_grade_info 정형 테이블 조회를 전담하는 함수
def get_esg_grade_from_lancedb(isu_cd: str, year: str = None, db_path: str = "/app/data/esg_lancedb"):
    try:
        import lancedb
        db = lancedb.connect(db_path)
        grade_table = db.open_table("tb_esg_grade_info")
        
        filters = [f"isu_cd = '{isu_cd}'"]
        if year and year.strip():
            # 🌟 1. 필터 조건: yy 대신 eval_year 사용
            # (만약 DB에 eval_year가 숫자형(int)으로 저장되어 있다면 '{year.strip()}' 대신 {year.strip()} 으로 따옴표를 빼주세요)
            filters.append(f"eval_year = '{year.strip()}'") 
            
        filter_str = " AND ".join(filters)
        df = grade_table.search().where(filter_str).to_pandas()
        
        if df.empty:
            return None
            
        record = df.iloc[0].to_dict()
        print(f"✅ ESG 등급 데이터 조회 성공: {record}")
        
        # 🌟 모든 기관의 데이터를 구조화된 JSON(Dict) 형태로 반환합니다.
        return {
            "com_abbrv": record.get("com_abbrv", "알수없음"),
            "isu_cd": record.get("isu_cd", "-"),
            # 🌟 2. 반환 데이터: yy 대신 eval_year에서 추출 (문자열로 안전하게 형변환)
            "target_year": str(record.get("eval_year", "-")),
            
            # 1. 한국ESG기준원 (KCGS) - E, S, G 상세 포함
            "kcgs": {
                "year": record.get("kcgs_yy", "-"),
                "esg": record.get("kcgs_esg", "-"),
                "env": record.get("kcgs_env", "-"),
                "soc": record.get("kcgs_soc", "-"),
                "gov": record.get("kcgs_gov", "-")
            },
            # 2. 기타 평가기관 (MSCI, S&P, KESG, 서스틴베스트)
            "msci": {"year": record.get("msci_yy", "-"), "esg": record.get("msci_esg", "-")},
            "sp": {"year": record.get("sp_yy", "-"), "esg": record.get("sp_esg", "-")},
            "kesg": {"year": record.get("kesg_yy", "-"), "esg": record.get("kesg_esg", "-")},
            "sv": {"year": record.get("sv_yy", "-"), "esg": record.get("sv_esg", "-")},

            # 3.기업문서링크
        # 🌟 3. 기업 공식 공시 보고서 링크 정보 추가
            "reports": {
                "sustainable_report": {
                    "acpt_no": record.get("acpt_no1", "-"),
                    "title": "지속가능경영보고서",
                    "url": make_viewer_url(record.get("acpt_no1", "-"))
                },
                "governance_report": {
                    "acpt_no": record.get("acpt_no2", "-"),
                    "title": "기업지배구조보고서",
                    "url": make_viewer_url(record.get("acpt_no2", "-"))
                }
            }
        }
    except Exception as e:
        print(f"🚨 데이터 조회 에러: {str(e)}")
        return None

# ==========================================
# 🌟 0. DB 조회 함수 (업그레이드: 정형 데이터 테이블 검사 및 판다스 직접 필터링)
# ==========================================
def get_company_data_years(db_path: str = "/app/data/esg_lancedb", isu_cd: str = None) -> list:
    """LanceDB를 조회하여 해당 기업의 대시보드 데이터(정형)가 존재하는 모든 연도 목록을 반환합니다."""
    try:
        import lancedb
        db = lancedb.connect(db_path)
        
        # 🌟 대시보드가 사용하는 정형 데이터 테이블을 검사합니다.
        if "tb_esg_grade_info" not in db.table_names():
            return []
            
        table = db.open_table("tb_esg_grade_info")
        
        # 🌟 LanceDB의 search() 대신 전체를 판다스로 가져와서 정확하게 필터링 (가장 확실한 방법)
        df = table.to_pandas()
        
        # 종목코드는 문자열로 변환하여 비교
        filtered_df = df[df['isu_cd'].astype(str) == str(isu_cd).strip()]
        
        if filtered_df.empty:
            return []
            
        # 존재하는 연도(eval_year) 중복 제거 후 최신순 정렬
        years = sorted(filtered_df['eval_year'].dropna().unique().tolist(), reverse=True)
        return [str(int(y)) if isinstance(y, float) else str(y) for y in years]
        
    except Exception as e:
        print(f"⚠️ DB 확인 중 오류 발생: {e}")
        return []