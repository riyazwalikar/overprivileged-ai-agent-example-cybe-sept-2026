.PHONY: env up down seed dryrun logs ps

env:
	./scripts/gen_env.sh

up:
	docker compose up -d --build

down:
	docker compose down

seed:
	docker compose exec support-agent python seed/seed.py
	docker compose exec ops-internal python seed/seed.py

dryrun:
	./scripts/dryrun.sh

logs:
	docker compose logs -f

ps:
	docker compose ps
