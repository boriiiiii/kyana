.PHONY: dev run front start test install setup ngrok tunnel

# Lancer le serveur en mode dev (avec hot-reload)
dev:
	. venv/bin/activate && uvicorn app.main:app --reload

# Lancer le serveur (sans reload)
run:
	. venv/bin/activate && uvicorn app.main:app

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

# Exposer le serveur local sur internet via ngrok (pour les webhooks Instagram)
ngrok:
	ngrok http 8000

# Lancer le frontend Next.js
front:
	cd frontend && npm run dev

# Lancer backend + frontend en parallèle
start:
	. venv/bin/activate && uvicorn app.main:app --reload & cd frontend && npm run dev

# Alias pratique
tunnel: ngrok
