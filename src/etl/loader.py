import lancedb
import pandas as pd
import json
from typing import Union, List
from langchain_community.vectorstores import LanceDB
from langchain_huggingface import HuggingFaceEmbeddings

class ESGLoader:
    def __init__(self, db_path: str = "./data/esg_lancedb"):
        self.db_path = db_path
        self.db = lancedb.connect(self.db_path)
        
        print("⏳ 임베딩 모델 로딩 중...")
        self.embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")

    # ==========================================
    # 1. 정형 데이터 로드 함수 (Upsert 방식)
    # ==========================================
    def load_structured_data(self, 
                             df: pd.DataFrame, 
                             table_name: str, 
                             pk: Union[str, List[str]]):
        """
        정형 데이터(DataFrame)를 DB에 적재합니다. (PK 기준으로 자동 Upsert)
        """
        if df is None or df.empty:
            print(f"⚠️ [{table_name}] 적재할 데이터가 없습니다.")
            return

        print(f"\n▶ [{table_name}] 정형 데이터 {len(df)}건 처리 중...")

        # PyArrow 변환 오류 방지
        df_to_save = df.copy()
        for col in df_to_save.columns:
            if df_to_save[col].dtype == 'object':
                df_to_save[col] = df_to_save[col].astype(str)

        # 테이블이 없을 경우 Create
        if table_name not in self.db.table_names():
            print(f"🆕 [{table_name}] 테이블을 생성하고 데이터를 적재합니다.")
            self.db.create_table(table_name, data=df_to_save)
        else:
            table = self.db.open_table(table_name)
            
            # PK 유효성 검사 후 Upsert 수행
            keys_to_check = [pk] if isinstance(pk, str) else pk
            if all(k in df_to_save.columns for k in keys_to_check):
                print(f"🔄 [{table_name}] PK {pk} 기준으로 데이터를 Upsert 합니다.")
                table.merge_insert(pk) \
                     .when_matched_update_all() \
                     .when_not_matched_insert_all() \
                     .execute(df_to_save)
            else:
                print(f"⚠️ [{table_name}] 데이터에 지정된 PK가 없습니다. 단순 추가(Append)합니다.")
                table.add(df_to_save)
                
        print(f"✅ [{table_name}] 정형 데이터 적재 완료!")

    # ==========================================
    # 2. 비정형 벡터 데이터 로드 함수 (Delete & Insert 방식)
    # ==========================================
    def load_vector_data(self, 
                         documents: list, 
                         table_name: str = "tb_esg_corp_gov_report", 
                         doc_id_key: str = "doc_id"):
        """
        비정형 데이터(문서 청크)를 DB에 적재합니다. 
        (LangChain 래퍼를 탈피하여 완전한 Flat Column 스키마로 최적화)
        """
        if not documents:
            print(f"⚠️ [{table_name}] 적재할 보고서 청크가 없습니다.")
            return

        print(f"\n▶ [{table_name}] 총 {len(documents)}개의 청크 임베딩 및 Flat 스키마 적재 중...")

        # 1. 문서 텍스트만 모아서 한 번에 임베딩 (속도 최적화)
        texts = [doc.page_content for doc in documents]
        embeddings = self.embeddings.embed_documents(texts)

        # 2. LangChain Document 객체를 해체하여 평탄화된(Flat) 리스트로 조립
        flat_data = []
        new_doc_ids = set()

        for doc, emb in zip(documents, embeddings):
            # doc_id 수집 (나중에 삭제 조건으로 사용)
            doc_id = doc.metadata.get(doc_id_key)
            if doc_id:
                new_doc_ids.add(doc_id)

            # 🌟 핵심: metadata 안의 값을 꺼내서 최상위 키로 올려버림 (Flat)
            row = {
                "text": doc.page_content,
                "vector": emb
            }
            # 딕셔너리 업데이트를 통해 chunk_id, eval_year 등이 모두 최상위 컬럼이 됨
            row.update(doc.metadata) 
            flat_data.append(row)

        # 3. LanceDB 네이티브 API를 사용하여 데이터 적재
        if table_name not in self.db.table_names():
            print(f"🆕 [{table_name}] Flat 스키마로 새 벡터 테이블을 생성합니다.")
            self.db.create_table(table_name, data=flat_data)
        else:
            table = self.db.open_table(table_name)
            
            # 중복 방지를 위한 기존 문서 삭제 로직 (이젠 metadata. 을 안 붙여도 됨!)
            if new_doc_ids:
                ids_str = ", ".join([f"'{id}'" for id in new_doc_ids])
                delete_condition = f"{doc_id_key} IN ({ids_str})" # 완벽하게 깔끔해진 SQL 조건
                
                try:
                    table.delete(delete_condition)
                    print(f"🗑️ [{table_name}] 기존 문서({delete_condition})의 구형 청크 삭제 완료")
                except Exception as e:
                    print(f"⚠️ [{table_name}] 삭제 과정 건너뜀: {e}")

            # Flat 데이터 직접 추가
            print(f"🔄 [{table_name}] 신규 Flat 청크 데이터를 추가합니다.")
            table.add(flat_data)
            
        print(f"✅ [{table_name}] 비정형 벡터 데이터 Flat 적재 완료!")