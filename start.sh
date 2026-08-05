# sudo docker compose build -d --build
# sudo docker compose run --rm esg-etl-job python -m src.etl.pipeline
# sudo docker compose run --rm esg-etl-job python -u main.py
# sudo docker compose up -d

sudo docker compose down
sudo docker compose up -d
sudo docker logs -f esg_api_server
# sudo docker compose run --rm esg-etl-job python -u main.py
