.PHONY: dev start migrate seed test worker consumer llm-worker logs

# Start everything: build images, run migrations, print service URLs, tail logs
start:
	@echo "\n==> Building and starting all services..."
	docker compose up -d --build
	@echo "\n==> Waiting for Django to be ready..."
	@until docker compose exec -T django python manage.py check --deploy 2>/dev/null || \
	       docker compose exec -T django python manage.py check 2>/dev/null; do \
	  printf '.'; sleep 2; done
	@echo "\n==> Running migrations..."
	docker compose exec django python manage.py migrate
	@echo "\n==> Seeding users..."
	docker compose exec django python manage.py seed_users
	@echo "\n"
	@echo "==========================================="
	@echo "  GraphCRM is running"
	@echo "==========================================="
	@echo "  Django Admin http://localhost:8000/admin/"
	@echo "  Django API   http://localhost:8000/api/"
	@echo "  WebSocket  ws://localhost:8000/ws/crm/"
	@echo "  Neo4j      http://localhost:7474"
	@echo "  RabbitMQ   http://localhost:15672"
	@echo "  ClickHouse http://localhost:8123"
	@echo "==========================================="
	@echo "  Tailing logs (Ctrl-C to stop watching,"
	@echo "  services keep running in background)"
	@echo "==========================================="
	docker compose logs -f django celery_worker celery_llm_worker

dev:
	docker compose up -d

down:
	docker compose down

build:
	docker compose up -d --build

migrate:
	docker compose exec django python manage.py migrate

seed:
	docker compose exec django python manage.py seed_users
	docker compose exec django python manage.py simulate_bookkeeper_events

test:
	docker compose exec django python manage.py test tests/

worker:
	docker compose exec django celery -A core worker -Q default -l info

llm-worker:
	docker compose exec django celery -A core worker -Q llm -l info -c 2

consumer:
	docker compose exec django python manage.py start_consumer

llm-consumer:
	docker compose exec django python manage.py start_llm_consumer

logs:
	docker compose logs -f
