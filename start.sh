# sudo docker compose build -d --build
# sudo docker compose run --rm esg-etl-job python -m src.etl.pipeline
# sudo docker compose run --rm esg-etl-job python -u main.py
# sudo docker compose up -d

sudo docker compose down
# ##환경변경시
# sudo docker-compose build --no-cache
##소스변경시
# sudo docker compose up -d
# ##전체실행
sudo docker compose up -d --build
sudo docker logs -f esg_api_server
# sudo docker compose run --rm esg-etl-job python -u main.py
