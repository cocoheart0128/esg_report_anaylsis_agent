import requests
import pandas as pd
import json
from bs4 import BeautifulSoup, NavigableString
from langchain_text_splitters import RecursiveCharacterTextSplitter

class ESGTransformer:
    def __init__(self, chunk_size=1500, chunk_overlap=200):
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,   
            chunk_overlap=chunk_overlap, 
            separators=["\n\n", "\n", ".", " "]
        )

    # ==========================================
    # 🌟 새로 추가된 브릿지 함수: DataFrame 행(Row) 처리
    # ==========================================
    def process_dataframe_row(self, row: pd.Series) -> list:
        """
        Extractor가 반환한 DataFrame의 한 행(Row)을 받아, 
        JSON 컬럼에서 URL을 파싱하고 메타데이터를 조립하여 청크 리스트를 반환합니다.
        """
        # 1. Extractor의 DataFrame 컬럼을 기반으로 메타데이터 조립
        base_metadata = {
            "acptno": str(row.get('acpt_no2', '')).strip(),
            "isu_cd": str(row.get('isu_cd', '')).strip(),
            "eval_year": str(row.get('eval_year', '0000')).strip(),
            "com_abbrv": str(row.get('com_abbrv', 'Unknown')).strip(),
            "doc_type": "지배구조보고서"  # 필요시 row에서 가져올 수 있음
        }

        if not base_metadata["acptno"]:
            return []

        # 2. JSON 파싱하여 URL 추출
        doc_json_str = row.get('acpt_no2_doc_json')
        if not doc_json_str or pd.isna(doc_json_str):
            return []

        try:
            doc_info = json.loads(doc_json_str)
            
            # main_docs의 첫 번째 문서를 타겟으로 설정
            if not doc_info.get("main_docs"):
                return []
            
            target_doc = doc_info["main_docs"][0]
            toc_url = target_doc.get("toc_url")
            main_url = target_doc.get("main_url")

            if not toc_url or not main_url:
                return []

            # (중요) KRX URL이 상대경로('/')로 시작할 경우 도메인을 붙여줍니다.
            base_domain = "https://kind.krx.co.kr"
            if toc_url.startswith("/"): toc_url = base_domain + toc_url
            if main_url.startswith("/"): main_url = base_domain + main_url

            # 3. 조립된 정보로 html_to_chunks 호출
            print(f"[{base_metadata['com_abbrv']} - {base_metadata['eval_year']}년] 텍스트 분할 중...")
            return self.html_to_chunks(toc_url, main_url, base_metadata)

        except Exception as e:
            print(f"⚠️ [{base_metadata['com_abbrv']}] 데이터 처리 중 오류: {e}")
            return []

    # ==========================================
    # 기존 코드 (유지)
    # ==========================================
    def html_to_chunks(self, toc_url: str, main_url: str, base_metadata: dict) -> list:
        # ... (이전에 작성된 코드와 동일) ...
        try:
            toc_list = self._parse_toc(toc_url)
            main_res = requests.get(main_url, headers=self.headers, verify=False)
            main_res.raise_for_status()
            body_soup = BeautifulSoup(main_res.content, 'html.parser')
            sections = self._extract_sections(body_soup, toc_list)
            
            doc_id = str(base_metadata.get("acptno", "unknown_doc"))
            
            final_chunks = []
            for sec in sections:
                if not sec['content'].strip(): continue
                
                eval_year_raw = str(base_metadata.get("eval_year", "0"))
                chunk_metadata = {
                    "doc_id": doc_id,
                    "eval_year": int(eval_year_raw) if eval_year_raw.isdigit() else 0,
                    "isu_cd": str(base_metadata.get("isu_cd", "Unknown")),
                    "com_abbrv": str(base_metadata.get("com_abbrv", "Unknown")),
                    "doc_type": str(base_metadata.get("doc_type", "지배구조보고서")),
                    "toc_name": sec['title'],
                    "access_level": "public"
                }
                
                chunks = self.text_splitter.create_documents(
                    texts=[sec['content']], metadatas=[chunk_metadata]
                )
                final_chunks.extend(chunks)
                
            for idx, chunk in enumerate(final_chunks):
                chunk.metadata["chunk_index"] = idx
                chunk.metadata["chunk_id"] = f"{doc_id}_chunk_{idx:04d}"
                
            return final_chunks
        except Exception as e:
            print(f"변환 중 오류 발생 (회사: {base_metadata.get('com_abbrv')}): {e}")
            return []

    def _parse_toc(self, toc_url: str) -> list:
        res = requests.get(toc_url, headers=self.headers, verify=False)
        soup = BeautifulSoup(res.content, 'html.parser')
        toc_list = []
        for a_tag in soup.find_all('a'):
            href = a_tag.get('href', '')
            if '#' in href:
                toc_list.append({
                    'title': a_tag.get_text(strip=True), 
                    'anchor': href.split('#')[-1]
                })
        return toc_list

    def _extract_sections(self, body_soup, toc_list: list) -> list:
        extracted = []
        for i in range(len(toc_list)):
            curr = toc_list[i]
            next_item = toc_list[i+1] if i + 1 < len(toc_list) else None

            start_node = body_soup.find('a', attrs={'name': curr['anchor']}) or body_soup.find(id=curr['anchor'])
            end_node = body_soup.find('a', attrs={'name': next_item['anchor']}) or body_soup.find(id=next_item['anchor']) if next_item else None

            if not start_node:
                continue 

            section_text = []
            curr_node = start_node.next_element
            while curr_node and curr_node != end_node:
                if isinstance(curr_node, NavigableString):
                    text = str(curr_node).strip()
                    if text:
                        section_text.append(text)
                curr_node = curr_node.next_element

            extracted.append({
                'title': curr['title'],
                'content': '\n'.join(section_text)
            })
        return extracted