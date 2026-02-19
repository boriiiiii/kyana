.PHONY: dev run test install setup

# Lancer le serveur en mode dev (avec hot-reload)
dev:
	uvicorn app.main:app --reload

# Lancer le serveur (sans reload)
run:
	uvicorn app.main:app

# Lancer les tests
test:
	pytest tests/ -v

# Installer les dépendances
install:
	pip install -r requirements.txt

# Setup complet (venv + dépendances)
setup:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cp -n .env.example .env 2>/dev/null || true
	@echo "✅ Setup terminé ! Active le venv : source venv/bin/activate"
