# Justfile for Users API

# Display available commands
default:
    @just --list

# Generate .env from template with a secure JWT secret
setup:
    ./scripts/init_env.sh

# Build and start the Docker containers
start:
	@if [ ! -f .env ]; then just setup; fi
	docker compose up --build

# Stop the Docker containers and clean volumes
stop:
    docker compose down -v

# Run the test suite inside a Docker container (mounts tests directory and runs pytest)
test:
	docker compose run --rm -v ./server/tests:/app/tests app pytest -o asyncio_mode=auto -o asyncio_default_fixture_loop_scope=function /app/tests

# View logs of the Celery worker service
logs-worker:
    docker compose logs -f celery_worker

# View logs of the Celery beat scheduler service
logs-beat:
    docker compose logs -f celery_beat

# View logs of all services
logs:
    docker compose logs -f

# Access the shell of the running app container
shell:
    docker compose exec app sh

# Access the PostgreSQL command line shell
db-shell:
    docker compose exec db psql -U postgres
