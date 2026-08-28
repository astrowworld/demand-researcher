# Demand Researcher — Design

## Objectif

Détecter sur Reddit des signaux de demande exprimée par des gens ("je cherche
X") pour repérer :

1. des **produits** que je peux racheter/revendre (ex: une 3DS craquée
   revendable après réparation) ;
2. des **prestations** recherchées (ex: quelqu'un cherche un développeur ou
   un freelance) — pour savoir quoi proposer moi-même.

Usage V1 : outil perso uniquement, pas de compte, pas de multi-utilisateur.
L'idée de le revendre un jour à des devs/prestataires en manque de clients
est notée mais **hors scope** de cette V1 — rien n'est construit en vue de
ça maintenant (pas d'auth, pas de séparation par tenant).

## Non-objectifs (V1)

- Pas de multi-utilisateur / SaaS.
- Pas de notification push (dashboard local uniquement).
- Pas de couverture d'autres plateformes (forums FR, Leboncoin, Discord) —
  Reddit uniquement pour commencer.
- Pas de recherche historique — uniquement les posts à partir du démarrage
  de l'outil.

## Architecture

Pipeline en 3 étages, dans la lignée de `pc-deal-scanner` / `techflip-scanner`.

### 1. Collecte

- API Reddit via PRAW (gratuite en lecture, usage non-commercial, 100
  requêtes/min avec OAuth — largement suffisant).
- Deux flux en parallèle :
  - **Firehose** : `reddit.subreddit("all").stream.submissions()` — capture
    n'importe quelle demande, sur n'importe quel subreddit ("tout et
    n'importe quoi").
  - **Subs ciblés prestations** : polling dédié sur `r/forhire`,
    `r/slavelabour` (vocabulaire standardisé, ex. flair "REQUEST") en plus
    du firehose, pour ne rien rater sur le volet prestations.
- Pas de dépendance à la recherche Reddit (limitée, pas d'historique) —
  seulement du streaming en temps réel, ce qui contourne cette limite.

### 2. Pré-filtre gratuit (regex)

Avant toute dépense LLM, filtrage du firehose par regex/mots-clés
d'intention de demande : "cherche", "recherche", "ISO", "looking for",
"need a dev/freelancer", "where can I buy", etc. (FR + EN). Ce filtre est
volontairement permissif (faux positifs acceptés) — l'objectif est
d'éliminer le gros du bruit du firehose sans jamais rater une vraie demande.

Le firehose étant volumineux, ce filtre tourne en local sur chaque
submission reçue, sans appel API supplémentaire.

### 3. Classification (LLM)

Chaque post ayant passé le pré-filtre est envoyé à Claude Haiku (coût
négligeable vu le faible volume post-filtre) avec un prompt structuré qui
retourne :

- `categorie` : `produit` / `prestation` / `bruit` (faux positif à ignorer)
- `quoi` : description courte de ce qui est recherché
- `score` : confiance 0-100 que c'est une demande exploitable
- `sub` + lien du post (traçabilité)

Tout est stocké en SQLite (table unique `signaux`), y compris les `bruit` à
score bas, pour pouvoir ajuster le regex de pré-filtre plus tard sans perdre
l'historique déjà classifié.

### 4. Restitution

Dashboard local (Flask, même style que `techflip-scanner`) :

- Liste triable par score/date
- Filtre par catégorie (produit/prestation/tout)
- Chaque ligne : quoi, subreddit d'origine, lien direct vers le post, score
- Pas de compte, pas d'auth

## Alternatives écartées

- **Tout en regex, sans LLM** : gratuit mais raterait les tournures
  indirectes de demande.
- **Recherche full-text Reddit sans firehose** : plus simple à requêter mais
  pas d'historique et couverture plus pauvre que le streaming complet.
- **F5Bot ou équivalent** : outil existant, gratuit, fait déjà de l'alerte
  mot-clé Reddit temps réel. Ne fait pas de classification produit/prestation
  ni de scoring ni de dashboard — ne couvre pas le besoin, mais confirme que
  la détection brute est un problème déjà résolu ; la valeur ajoutée de cet
  outil est la classification et le scoring, pas la détection.

## Points d'attention

- **ToS Reddit** : usage non-commercial confirmé pour la lecture API en
  usage personnel/perso-bot. L'utilisation des signaux pour informer une
  activité de revente personnelle n'est pas de la revente des données
  Reddit elles-mêmes — pas un usage commercial de l'API au sens de Reddit,
  mais point à garder en tête si l'outil grossit.
- **Coût LLM** : maîtrisé par le pré-filtre regex qui réduit drastiquement
  le volume envoyé à Haiku.
