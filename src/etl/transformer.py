import requests
import pandas as pd
import json
from bs4 import BeautifulSoup, NavigableString
from langchain_text_splitters import RecursiveCharacterTextSplitter
from urllib.parse import urljoin, urlparse
import pdfplumber
from io import BytesIO

class ESGTransformer:
    def __init__(self, chunk_size=1500, chunk_overlap=200, max_depth=2):
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " "]
        )
        self.visited_urls = set()
        self.max_depth = max_depth

    def _ensure_absolute_url(self, url: str, base_url: str = None) -> str:
        """상대경로 URL을 절대경로로 변환"""
        if not url:
            return None
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return "https://kind.krx.co.kr" + url
        if base_url:
            return urljoin(base_url, url)
        return "https://kind.krx.co.kr" + url

    def process_dataframe_row(self, row: pd.Series) -> list:
        """DataFrame 행 처리 및 모든 링크 청킹"""
        all_chunks = []
        self.visited_urls.clear()
        
        base_metadata = {
            "isu_cd": str(row.get('isu_cd', '')).strip(),
            "eval_year": str(row.get('eval_year', '0000')).strip(),
            "com_abbrv": str(row.get('com_abbrv', 'Unknown')).strip(),
        }

        json_targets = [
            ('acpt_no1_doc_json', str(row.get('acpt_no1', '')).strip(), '지속가능경영보고서'),
            ('acpt_no2_doc_json', str(row.get('acpt_no2', '')).strip(), '기업지배구조보고서')
        ]

        for col_name, acptno, default_doc_type in json_targets:
            if not acptno or acptno.lower() == 'nan' or acptno == 'None':
                continue
            
            doc_json_str = row.get(col_name)
            if not doc_json_str or pd.isna(doc_json_str):
                continue

            try:
                doc_info = json.loads(doc_json_str)
                for doc_category in ["main_docs", "attached_docs"]:
                    for doc in doc_info.get(doc_category, []):
                        toc_url = self._ensure_absolute_url(doc.get("toc_url"))
                        main_url = self._ensure_absolute_url(doc.get("main_url"))

                        if not main_url:
                            continue

                        metadata = base_metadata.copy()
                        metadata["acptno"] = acptno
                        metadata["doc_type"] = f"{default_doc_type}_첨부파일" if doc_category == "attached_docs" else default_doc_type

                        print(f"[{metadata['com_abbrv']} - {metadata['eval_year']}년] {metadata['doc_type']} 파싱 중...")
                        chunks = self._process_url(main_url, toc_url, metadata, depth=0)
                        all_chunks.extend(chunks)

            except Exception as e:
                print(f"⚠️ [{base_metadata['com_abbrv']}] {col_name} 처리 오류: {e}")

        return all_chunks

    def _process_url(self, url: str, toc_url: str = None, base_metadata: dict = None, depth: int = 0) -> list:
        """URL 처리 (HTML/PDF 자동 판별 + 재귀)"""
        if url in self.visited_urls or depth > self.max_depth:
            return []
        
        self.visited_urls.add(url)
        chunks = []

        try:
            if url.lower().endswith('.pdf'):
                chunks = self._process_pdf(url, base_metadata)
            else:
                chunks = self._process_html(url, toc_url, base_metadata, depth)
        except Exception as e:
            print(f"⚠️ URL 처리 오류 ({url}): {e}")

        return chunks

    def _process_html(self, url: str, toc_url: str, metadata: dict, depth: int) -> list:
        """HTML 처리 및 내부 링크 재귀 추출"""
        chunks = []
        res = requests.get(url, headers=self.headers, verify=False, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.content, 'html.parser')

        # 1. 현재 HTML 청킹
        sections = []
        if toc_url:
            toc_list = self._parse_toc(toc_url)
            if toc_list:
                sections = self._extract_sections(soup, toc_list)
        
        if not sections:
            for script in soup(["script", "style"]):
                script.extract()
            raw_text = soup.get_text(separator='\n')
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            sections = [{'title': '전체 문서', 'content': '\n'.join(lines)}]

        for sec in sections:
            if not sec['content'].strip():
                continue
            chunks.extend(self._create_chunks(sec['content'], sec['title'], metadata))

        # 2. 내부 링크 재귀 처리 (PDF, 문서 링크)
        if depth < self.max_depth:
            links = self._extract_document_links(soup, url)
            for link_url, link_title in links:
                abs_url = self._ensure_absolute_url(link_url, url)
                if abs_url not in self.visited_urls:
                    link_metadata = metadata.copy()
                    link_metadata["doc_type"] = f"{metadata.get('doc_type', 'Unknown')}_{link_title}"
                    sub_chunks = self._process_url(abs_url, None, link_metadata, depth + 1)
                    chunks.extend(sub_chunks)

        return chunks

    def _process_pdf(self, url: str, metadata: dict) -> list:
        """PDF 다운로드 및 텍스트 추출"""
        chunks = []
        try:
            res = requests.get(url, headers=self.headers, verify=False, timeout=10)
            res.raise_for_status()
            
            with pdfplumber.open(BytesIO(res.content)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        chunks.extend(self._create_chunks(
                            text,
                            f"PDF_Page_{page_idx + 1}",
                            metadata
                        ))
        except Exception as e:
            print(f"⚠️ PDF 처리 실패 ({url}): {e}")

        return chunks

    def _extract_document_links(self, soup: BeautifulSoup, base_url: str) -> list:
        """HTML에서 PDF 및 문서 링크 추출"""
        links = []
        doc_extensions = ('.pdf', '.docx', '.xlsx', '.pptx', '.hwp')
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '').lower()
            if any(href.endswith(ext) for ext in doc_extensions):
                title = a_tag.get_text(strip=True) or href.split('/')[-1]
                links.append((a_tag.get('href'), title[:30]))  # 제목 길이 제한
        
        return links

    def _create_chunks(self, text: str, title: str, metadata: dict) -> list:
        """텍스트를 청크로 분할"""
        chunk_metadata = {
            "doc_id": str(metadata.get("acptno", "unknown")),
            "eval_year": int(str(metadata.get("eval_year", "0")).split()[0]) if str(metadata.get("eval_year", "0")).isdigit() else 0,
            "isu_cd": str(metadata.get("isu_cd", "Unknown")),
            "com_abbrv": str(metadata.get("com_abbrv", "Unknown")),
            "doc_type": str(metadata.get("doc_type", "Unknown")),
            "toc_name": title,
            "access_level": "public"
        }
        
        chunks = self.text_splitter.create_documents([text], [chunk_metadata])
        
        for idx, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = idx
            chunk.metadata["chunk_id"] = f"{chunk_metadata['doc_id']}_{metadata.get('doc_type', 'Unknown').replace(' ', '_')}_chunk_{idx:04d}"
        
        return chunks

    def _parse_toc(self, toc_url: str) -> list:
        """목차 파싱"""
        try:
            res = requests.get(toc_url, headers=self.headers, verify=False, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.content, 'html.parser')
            
            return [
                {'title': a.get_text(strip=True), 'anchor': a.get('href', '').split('#')[-1]}
                for a in soup.find_all('a') if '#' in a.get('href', '')
            ]
        except Exception as e:
            print(f"⚠️ 목차 파싱 오류: {e}")
            return []

    def _extract_sections(self, soup, toc_list: list) -> list:
        """목차 기반 섹션 추출"""
        extracted = []
        for i, curr in enumerate(toc_list):
            next_item = toc_list[i + 1] if i + 1 < len(toc_list) else None
            
            start_node = soup.find('a', attrs={'name': curr['anchor']}) or soup.find(id=curr['anchor'])
            end_node = (soup.find('a', attrs={'name': next_item['anchor']}) or 
                       soup.find(id=next_item['anchor'])) if next_item else None

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


# import requests
# import pandas as pd
# import json
# from bs4 import BeautifulSoup, NavigableString
# from langchain_text_splitters import RecursiveCharacterTextSplitter

# class ESGTransformer:
#     def __init__(self, chunk_size=1500, chunk_overlap=200):
#         self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
#         self.text_splitter = RecursiveCharacterTextSplitter(
#             chunk_size=chunk_size,   
#             chunk_overlap=chunk_overlap, 
#             separators=["\n\n", "\n", ".", " "]
#         )

#     # ==========================================
#     # 🌟 새로 추가된 브릿지 함수: DataFrame 행(Row) 처리
#     # ==========================================
#     def process_dataframe_row(self, row: pd.Series) -> list:
#         """
#         Extractor가 반환한 DataFrame의 한 행(Row)을 받아, 
#         JSON 컬럼에서 URL을 파싱하고 메타데이터를 조립하여 청크 리스트를 반환합니다.
#         """
#         # 1. Extractor의 DataFrame 컬럼을 기반으로 메타데이터 조립
#         base_metadata = {
#             "acptno": str(row.get('acpt_no2', '')).strip(),
#             "isu_cd": str(row.get('isu_cd', '')).strip(),
#             "eval_year": str(row.get('eval_year', '0000')).strip(),
#             "com_abbrv": str(row.get('com_abbrv', 'Unknown')).strip(),
#             "doc_type": "지배구조보고서"  # 필요시 row에서 가져올 수 있음
#         }

#         if not base_metadata["acptno"]:
#             return []

#         # 2. JSON 파싱하여 URL 추출
#         doc_json_str = row.get('acpt_no2_doc_json')
#         if not doc_json_str or pd.isna(doc_json_str):
#             return []

#         try:
#             doc_info = json.loads(doc_json_str)
            
#             # main_docs의 첫 번째 문서를 타겟으로 설정
#             if not doc_info.get("main_docs"):
#                 return []
            
#             target_doc = doc_info["main_docs"][0]
#             toc_url = target_doc.get("toc_url")
#             main_url = target_doc.get("main_url")

#             if not toc_url or not main_url:
#                 return []

#             # (중요) KRX URL이 상대경로('/')로 시작할 경우 도메인을 붙여줍니다.
#             base_domain = "https://kind.krx.co.kr"
#             if toc_url.startswith("/"): toc_url = base_domain + toc_url
#             if main_url.startswith("/"): main_url = base_domain + main_url

#             # 3. 조립된 정보로 html_to_chunks 호출
#             print(f"[{base_metadata['com_abbrv']} - {base_metadata['eval_year']}년] 텍스트 분할 중...")
#             return self.html_to_chunks(toc_url, main_url, base_metadata)

#         except Exception as e:
#             print(f"⚠️ [{base_metadata['com_abbrv']}] 데이터 처리 중 오류: {e}")
#             return []

#     # ==========================================
#     # 기존 코드 (유지)
#     # ==========================================
#     def html_to_chunks(self, toc_url: str, main_url: str, base_metadata: dict) -> list:
#         # ... (이전에 작성된 코드와 동일) ...
#         try:
#             toc_list = self._parse_toc(toc_url)
#             main_res = requests.get(main_url, headers=self.headers, verify=False)
#             main_res.raise_for_status()
#             body_soup = BeautifulSoup(main_res.content, 'html.parser')
#             sections = self._extract_sections(body_soup, toc_list)
            
#             doc_id = str(base_metadata.get("acptno", "unknown_doc"))
            
#             final_chunks = []
#             for sec in sections:
#                 if not sec['content'].strip(): continue
                
#                 eval_year_raw = str(base_metadata.get("eval_year", "0"))
#                 chunk_metadata = {
#                     "doc_id": doc_id,
#                     "eval_year": int(eval_year_raw) if eval_year_raw.isdigit() else 0,
#                     "isu_cd": str(base_metadata.get("isu_cd", "Unknown")),
#                     "com_abbrv": str(base_metadata.get("com_abbrv", "Unknown")),
#                     "doc_type": str(base_metadata.get("doc_type", "지배구조보고서")),
#                     "toc_name": sec['title'],
#                     "access_level": "public"
#                 }
                
#                 chunks = self.text_splitter.create_documents(
#                     texts=[sec['content']], metadatas=[chunk_metadata]
#                 )
#                 final_chunks.extend(chunks)
                
#             for idx, chunk in enumerate(final_chunks):
#                 chunk.metadata["chunk_index"] = idx
#                 chunk.metadata["chunk_id"] = f"{doc_id}_chunk_{idx:04d}"
                
#             return final_chunks
#         except Exception as e:
#             print(f"변환 중 오류 발생 (회사: {base_metadata.get('com_abbrv')}): {e}")
#             return []

#     def _parse_toc(self, toc_url: str) -> list:
#         res = requests.get(toc_url, headers=self.headers, verify=False)
#         soup = BeautifulSoup(res.content, 'html.parser')
#         toc_list = []
#         for a_tag in soup.find_all('a'):
#             href = a_tag.get('href', '')
#             if '#' in href:
#                 toc_list.append({
#                     'title': a_tag.get_text(strip=True), 
#                     'anchor': href.split('#')[-1]
#                 })
#         return toc_list

#     def _extract_sections(self, body_soup, toc_list: list) -> list:
#         extracted = []
#         for i in range(len(toc_list)):
#             curr = toc_list[i]
#             next_item = toc_list[i+1] if i + 1 < len(toc_list) else None

#             start_node = body_soup.find('a', attrs={'name': curr['anchor']}) or body_soup.find(id=curr['anchor'])
#             end_node = body_soup.find('a', attrs={'name': next_item['anchor']}) or body_soup.find(id=next_item['anchor']) if next_item else None

#             if not start_node:
#                 continue 

#             section_text = []
#             curr_node = start_node.next_element
#             while curr_node and curr_node != end_node:
#                 if isinstance(curr_node, NavigableString):
#                     text = str(curr_node).strip()
#                     if text:
#                         section_text.append(text)
#                 curr_node = curr_node.next_element

#             extracted.append({
#                 'title': curr['title'],
#                 'content': '\n'.join(section_text)
#             })
#         return extracted