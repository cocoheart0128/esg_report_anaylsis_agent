import requests
import re
import pandas as pd
import urllib3
import time
import json  # 추가됨
from bs4 import BeautifulSoup  # 추가됨
from concurrent.futures import ThreadPoolExecutor  # 추가됨

########################################################################################
##############입력된 기업코드/명 기반으로 ESG 데이터 수집 및 JSON 추출 클래스 정의##############
########################################################################################

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ESGExtractor:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }

    def fetch_esg_data(self, start_yr="", end_yr="", isu_cd="") -> pd.DataFrame:
        """KRX ESG 포털에서 연도별 대상 기업 목록을 수집합니다."""
        url = "https://esg.krx.co.kr/contents/99/ESG99000001.jspx"
        df_list = []
        
        for year in range(int(start_yr), int(end_yr) + 1):
            payload = {
                "isu_cd": isu_cd,
                "sch_yy": str(year),
                "upjong": "all",
                "pagePath": "/contents/02/02020000/ESG02020000.jsp",
                "code": "02/02020000/esg02020000"
            }
            try:
                resp = requests.post(url, data=payload, headers=self.headers, verify=False)
                resp.raise_for_status()
                data = resp.json()
                
                records = data.get("block1", [])
                if not records and data.keys():
                    records = data[list(data.keys())[0]]
                    
                if records:
                    temp_df = pd.DataFrame(records)
                    temp_df['eval_year'] = str(year)
                    df_list.append(temp_df)
            except Exception as e:
                print(f"[{year}년] 목록 수집 오류: {e}")
            time.sleep(0.5)
            
        return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

    def _get_krx_doc_nos(self, acptno: str) -> dict:
        url = f"https://kind.krx.co.kr/common/disclsviewer.do?method=search&acptno={acptno}"
        result = {'main_doc_nos': [], 'attached_doc_nos': []}
        try:
            resp = requests.get(url, headers=self.headers, verify=False, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            main_doc = soup.find('select', {'id': 'mainDoc'})
            if main_doc:
                for opt in main_doc.find_all('option'):
                    val = opt.get('value', '').strip()
                    if val:
                        result['main_doc_nos'].append(val.split('|')[0])

            attached_doc = soup.find('select', {'id': 'attachedDoc'})
            if attached_doc:
                for opt in attached_doc.find_all('option'):
                    val = opt.get('value', '').strip()
                    if val:
                        result['attached_doc_nos'].append(val.split('|')[0])
        except Exception:
            pass
        return result

    def _fetch_urls_by_docno(self, doc_no: str) -> dict:
        url = 'https://kind.krx.co.kr/common/disclsviewer.do'
        params = {'method': 'searchContents', 'docNo': doc_no}
        result = {'toc_url': None, 'main_url': None}
        try:
            resp = requests.get(url, params=params, headers=self.headers, verify=False, timeout=10)
            match = re.search(r'parent\.setPath\((.*?)\);', resp.text, re.DOTALL)
            if match:
                paths = re.findall(r"['\"]([^'\"]*)['\"]", match.group(1))
                for item in paths:
                    if item.endswith('_toc.htm'):
                        result['toc_url'] = item
                    elif item.endswith('.htm'):
                        result['main_url'] = item
        except Exception:
            pass
        return result

    # 수정됨: self 추가
    def _get_full_json(self, acptno):
        """acptno가 주어지면 전체 문서 정보를 JSON 문자열로 반환"""
        if pd.isna(acptno) or str(acptno).strip() == "":
            return None

        acptno = str(acptno).strip()
        doc_nos = self._get_krx_doc_nos(acptno)
        
        final_result = {
            "acptno": acptno,
            "main_docs": [],
            "attached_docs": []
        }
        
        for doc_no in doc_nos['main_doc_nos']:
            urls = self._fetch_urls_by_docno(doc_no)
            final_result["main_docs"].append({
                "doc_no": doc_no,
                "toc_url": urls['toc_url'],
                "main_url": urls['main_url']
            })
            
        for doc_no in doc_nos['attached_doc_nos']:
            urls = self._fetch_urls_by_docno(doc_no)
            final_result["attached_docs"].append({
                "doc_no": doc_no,
                "toc_url": urls['toc_url'],
                "main_url": urls['main_url']
            })
        
        # 수정됨: 들여쓰기 교정
        return json.dumps(final_result, ensure_ascii=False)

    def fetch_full_esg_data(self, start_yr="", end_yr="", isu_cd="") -> pd.DataFrame:
        """데이터 수집부터 병렬 JSON 추출까지 전체 파이프라인을 실행합니다."""
        print("=== 1. ESG 데이터 수집 시작 ===")
        
        # 내부 메서드 호출은 self. 를 사용합니다.
        df = self.fetch_esg_data(start_yr=start_yr, end_yr=end_yr, isu_cd=isu_cd)
        
        if df.empty:
            print("수집된 데이터가 없습니다.")
            return df
            
        # 🌟 acpt_no1 데이터 추출 추가
        if 'acpt_no1' in df.columns:
            print("\n=== 2. acpt_no1 기반 문서 JSON 병렬 추출 시작 ===")
            print(f"총 {len(df)}건의 데이터 중 acpt_no1이 존재하는 행을 처리합니다. 잠시만 기다려주세요...")
            
            with ThreadPoolExecutor(max_workers=15) as executor:
                json_results_1 = list(executor.map(self._get_full_json, df['acpt_no1']))
                
            df['acpt_no1_doc_json'] = json_results_1
        else:
            print("\n수집된 데이터에 'acpt_no1' 컬럼이 존재하지 않습니다.")

        # acpt_no2 데이터 추출
        if 'acpt_no2' in df.columns:
            print("\n=== 3. acpt_no2 기반 문서 JSON 병렬 추출 시작 ===")
            print(f"총 {len(df)}건의 데이터 중 acpt_no2가 존재하는 행을 처리합니다. 잠시만 기다려주세요...")
            
            with ThreadPoolExecutor(max_workers=15) as executor:
                json_results_2 = list(executor.map(self._get_full_json, df['acpt_no2']))
                
            df['acpt_no2_doc_json'] = json_results_2
        else:
            print("\n수집된 데이터에 'acpt_no2' 컬럼이 존재하지 않습니다.")
            
        print("\n=== 모든 JSON 추출 작업 완료 ===")
        
        # 최종 완성된 DataFrame을 반환하여 외부에서(CSV 저장 등) 활용할 수 있게 합니다.
        return df

# # ==========================================
# # 메인 실행부 (매우 간결해짐)
# # ==========================================
# if __name__ == "__main__":
#     extractor = ESGExtractor()
    
#     # 묶어놓은 파이프라인 메서드 단 1줄만 호출
#     final_df = extractor.fetch_full_esg_data(start_yr="2024", end_yr="2026", isu_cd="282330")