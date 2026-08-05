from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.services.rag_service import ESGRagService
import traceback  # 🌟 추가 1: 에러 상세 추적 라이브러리

app = FastAPI(title="ESG AI Analyst Agent")
rag_service = ESGRagService()

class AnalyzeRequest(BaseModel):
    query: str
    llm_provider: str = "gemini"
    isu_cd: Optional[str] = None
    year: Optional[str] = None

@app.post("/api/analyze")
async def analyze_esg_report(req: AnalyzeRequest):
    try:
        result = rag_service.analyze_esg(
            query=req.query,
            llm_provider=req.llm_provider,
            isu_cd=req.isu_cd,
            year=req.year
        )
        return {"status": "success", "llm_used": req.llm_provider, "answer": result}
    except Exception as e:
        # 🌟 추가 2: 에러가 나면 숨기지 말고 터미널에 빨간색으로 쫙 뿌려주도록 설정!
        print("\n" + "="*50)
        print("🚨 [에러 발생] 서버 내부에서 문제가 터졌습니다!")
        traceback.print_exc() 
        print("="*50 + "\n")
        raise HTTPException(status_code=500, detail=str(e))