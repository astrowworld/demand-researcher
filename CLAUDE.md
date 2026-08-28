# demand-researcher

Détecte en temps réel sur Reddit les posts qui expriment une demande
("je cherche X") et les classe en `produit` (revendable) ou `prestation`
(service recherché), pour savoir quoi proposer. Outil perso, pas de
compte, pas de SaaS — voir `docs/superpowers/specs/2026-08-28-demand-researcher-design.md`.

## Architecture

- `config.py` — constantes : subs ciblés, mots-clés regex, modèle Claude.
- `db.py` — schéma SQLite (table `signaux`) + insert/lecture avec dédup par `reddit_id`.
- `prefilter.py` — filtre regex d'intention de demande, tourne avant tout
  appel LLM pour maîtriser le coût.
- `classifier.py` — appel Claude Haiku, retourne `{categorie, quoi, score}`.
- `reddit_client.py` — wrapper PRAW (lecture seule), génère un flux de
  submissions pour un subreddit donné.
- `collector.py` — `process_submission()` (pur, testé) applique
  pré-filtre → classification → stockage pour une submission ; `run_collector()`
  lance un thread par source (`r/all` + subs ciblés) et tourne en continu.
- `app.py` + `templates/index.html` — dashboard Flask local, triable/filtrable
  par catégorie.
- `run_collector.py` — entrypoint du collector (à lancer en tâche de fond).

## Lancer

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # puis remplir les clés
python run_collector.py &   # collecteur en fond
python app.py                # dashboard sur http://127.0.0.1:5000
```
