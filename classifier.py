import json

import anthropic

import config

VALID_CATEGORIES = {"produit", "prestation", "bruit"}

SYSTEM_PROMPT = (
    "Tu classes un post Reddit pour savoir s'il exprime une demande "
    "exploitable. Réponds UNIQUEMENT avec un JSON de la forme "
    '{"categorie": "produit"|"prestation"|"bruit", "quoi": "description courte", '
    '"score": 0-100}. "produit" = quelqu\'un cherche un produit physique à '
    "acheter. \"prestation\" = quelqu'un cherche un service/freelance/développeur. "
    "\"bruit\" = ce n'est pas une vraie demande (annonce, discussion générale, etc.)."
)


def parse_classification(raw_text: str) -> dict:
    data = json.loads(raw_text)
    categorie = data["categorie"]
    if categorie not in VALID_CATEGORIES:
        raise ValueError(f"Unknown categorie: {categorie!r}")
    return {
        "categorie": categorie,
        "quoi": data["quoi"],
        "score": int(data["score"]),
    }


def classify_post(title: str, body: str, client=None) -> dict:
    if client is None:
        client = anthropic.Anthropic()

    user_content = f"Titre: {title}\nTexte: {body or '(vide)'}"
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw_text = response.content[0].text
    return parse_classification(raw_text)
