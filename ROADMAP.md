# IA_Trade — Roadmap

## Priorité 1 — Bloque une candidature BNP

- [ ] **Déploiement en ligne** — Railway (Flask) + Vercel (Angular) → URL live à mettre dans le CV (1-2h)
- [x] **Métriques financières réelles**
  - Sharpe Ratio : `(avg_return - risk_free_rate) / std_return`
  - Max Drawdown : pire perte depuis le plus haut
  - Win Rate par actif
- [ ] **Screenshots dans le README** — prendre les captures et les push dans `docs/screenshots/`

---

## Priorité 2 — Niveau technique

- [x] **XGBoost** — comparer Random Forest vs XGBoost (accuracy + F1 par classe) dans un tableau
- [x] **Indicateur MACD** — ajouter `macd`, `macd_signal`, `macd_diff` via `ta` comme features ML
- [x] **Plus d'actifs** — BTC-USD, AAPL, ^GSPC + sélecteur dynamique Angular (plus de hardcode)

---

## Priorité 3 — Impressionne vraiment

- [ ] **Sentiment analysis** — NewsAPI + FinBERT (`ProsusAI/finbert`) → score sentiment comme feature ML + affiché dans le dashboard
- [ ] **WebSocket live** — Socket.IO push toutes les 60s, Angular consomme en temps réel

---

## Notes

- Venv Python : `source "ia bot trading/.venv/bin/activate"`
- Dev Angular : `cd trading-dashboard && npm start`
