FROM python:3.10-slim

WORKDIR /app

# 시스템 필수 패키지 설치
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY ./src ./src
COPY ./data ./data
COPY main.py .
COPY app.py .

RUN chmod -R 777 /app/data

# 컨테이너 실행 시 파이프라인 실행
# CMD ["python", "-m", "src.etl.pipeline"]

# FastAPI(8000)와 Streamlit(8501) 포트 개방 (도커 문서화 용도)
EXPOSE 8000
EXPOSE 8501

# 기본 실행 명령어 (docker-compose가 덮어씌우므로 기본값으로 둠)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]