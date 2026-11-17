.PHONY: api web test
api:
	cd apps/api && python -m uvicorn app.main:app --reload
web:
	cd apps/web && npm run dev
test:
	cd apps/api && python -m pytest -q
	cd apps/web && npm run test && npm run lint && npm run build
