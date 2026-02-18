.PHONY: build up down logs shell test lint

build:
	podman-compose build

up:
	podman-compose up -d

down:
	podman-compose down

logs:
	podman-compose logs -f

shell:
	podman-compose exec api bash

test:
	podman-compose exec api pytest tests/ -v

lint:
	podman-compose exec api ruff check app/
