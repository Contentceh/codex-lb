.PHONY: help up down logs ps health pull

help:
	@echo "codex-lb (production compose)"
	@echo "  make up      - start stack (docker-compose.prod.yml)"
	@echo "  make down    - stop stack"
	@echo "  make logs    - follow logs"
	@echo "  make ps      - container status"
	@echo "  make health  - curl local /health"
	@echo "  make pull    - pull image"

up:
	docker compose -f docker-compose.prod.yml up -d

down:
	docker compose -f docker-compose.prod.yml down

logs:
	docker compose -f docker-compose.prod.yml logs -f

ps:
	docker compose -f docker-compose.prod.yml ps

health:
	curl -fsS http://127.0.0.1:2455/health && echo

pull:
	docker compose -f docker-compose.prod.yml pull
