import requests
import pandas as pd
import json
import hashlib
import re
from bs4 import BeautifulSoup, NavigableString
from langchain_text_splitters import RecursiveCharacterTextSplitter
from urllib.parse import urljoin, urlparse, unquote
import pdfplumber
from io import BytesIO
from datetime import datetime, timezone
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

    def _extract_publish_dt(self, url: str) -> str:
        """KRX URL 경로에서 공시일(YYYY/MM/DD)을 추출"""
        if not url:
            return None

        match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", urlparse(url).path)
        return "-".join(match.groups()) if match else None

    def _get_publish_dt(self, row: pd.Series, doc: dict, main_url: str) -> str:
        """명시된 공시일을 우선 사용하고 없으면 KRX URL에서 추출"""
        for value in (doc.get("publish_dt"), row.get("publish_dt")):
            if value is not None and not pd.isna(value) and str(value).strip():
                return str(value).strip()
        return self._extract_publish_dt(main_url)

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
                        metadata["doc_se"] = default_doc_type
                        metadata["doc_category"] = "attached" if doc_category == "attached_docs" else "main"
                        metadata["publish_dt"] = self._get_publish_dt(row, doc, main_url)

                        print(f"[{metadata['com_abbrv']} - {metadata['eval_year']}년] {metadata['doc_se']} 파싱 중...")
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
            print(f"[URL 처리 완료] {url} | chunks: {len(chunks)}")
        except Exception as e:
            print(f"⚠️ URL 처리 오류 ({url}): {e}")
            print(f"[URL 처리 결과] {url} | chunks: 0")

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
            chunks.extend(self._create_chunks(
                sec['content'],
                sec['title'],
                metadata,
                source_link=url
            ))

        # 2. 내부 링크 재귀 처리 (PDF, 문서 링크)
        if depth < self.max_depth:
            links = self._extract_document_links(soup, url)
            for link_url, link_title in links:
                abs_url = self._ensure_absolute_url(link_url, url)
                if abs_url not in self.visited_urls:
                    link_metadata = metadata.copy()
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
                            metadata,
                            source_link=url,
                            page_number=page_idx + 1
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

    def _create_chunks(
        self,
        text: str,
        title: str,
        metadata: dict,
        source_link: str,
        page_number: int = None
    ) -> list:
        """텍스트를 청크로 분할"""
        path_name = unquote(urlparse(source_link).path.rsplit('/', 1)[-1])
        source_title = path_name or title
        suffix = source_title.rsplit('.', 1)[-1].lower() if '.' in source_title else ''
        doc_type = 'html' if suffix in ('htm', 'html', '') else suffix
        source_key = hashlib.sha1(source_link.encode('utf-8')).hexdigest()[:10]

        chunk_metadata = {
            "doc_id": str(metadata.get("acptno", "unknown")),
            "eval_year": int(str(metadata.get("eval_year", "0")).split()[0]) if str(metadata.get("eval_year", "0")).isdigit() else 0,
            "isu_cd": str(metadata.get("isu_cd", "Unknown")),
            "com_abbrv": str(metadata.get("com_abbrv", "Unknown")),
            "doc_se": str(metadata.get("doc_se", "Unknown")),
            "doc_category": str(metadata.get("doc_category", "main")),
            "publish_dt": metadata.get("publish_dt"),
            "doc_type": doc_type,
            "source_link": source_link,
            "source_title": source_title,
            "toc_name": title,
            "page_number": page_number or 0,
            "access_level": "public"
        }
        
        chunks = self.text_splitter.create_documents([text], [chunk_metadata])
        
        for idx, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = idx
            chunk.metadata["chunk_id"] = f"{chunk_metadata['doc_id']}_{source_key}_chunk_{idx:04d}"
            chunk.metadata["content_hash"] = hashlib.sha256(
                f"{source_link}\n{chunk.page_content}".encode("utf-8")
            ).hexdigest()
            chunk.metadata["fetched_at"] = datetime.now(timezone.utc).isoformat()
        
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