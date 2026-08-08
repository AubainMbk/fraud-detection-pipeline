"""
Garde-fou anti-hallucination : vérifie que les faits numériques critiques
du contexte (seuils, montants, délais) apparaissent dans la réponse générée.
Un signal simple mais concret, particulièrement adapté à un contexte bancaire
où les chiffres exacts (seuils de score, délais réglementaires) ne doivent
jamais être approximés ou inventés.
"""
import re


def extract_key_facts(text: str) -> set[str]:
    patterns = [
        r'\d+[.,]?\d*\s*%',
        r'\d+[.,]?\d*\s*(?:EUR|€)',
        r'\d+\s*(?:heures?|jours?|ans?)',
        r'0[.,]\d+',
    ]
    facts = set()
    for pattern in patterns:
        facts.update(m.lower().replace(" ", "") for m in re.findall(pattern, text, flags=re.IGNORECASE))
    return facts


def check_groundedness(context: str, answer: str) -> dict:
    context_facts = extract_key_facts(context)
    answer_facts = extract_key_facts(answer)
    missing = context_facts - answer_facts

    if not context_facts:
        coverage_ratio = None  # Rien à vérifier -- ne pas confondre avec un succès
    else:
        coverage_ratio = 1 - (len(missing) / len(context_facts))

    return {
        "context_facts": context_facts,
        "answer_facts": answer_facts,
        "missing_from_answer": missing,
        "coverage_ratio": coverage_ratio,
    }
