# FraudLens — RAG documentaire : notes techniques et pièges rencontrés

Ce document retrace la construction de la brique RAG de FraudLens : architecture,
vocabulaire clé, et cinq pièges réels rencontrés en cours de route — chacun avec son
symptôme, sa cause racine, son correctif, et le principe général à en retenir.
L'objectif : pouvoir en discuter précisément en entretien, pas juste dire "j'ai fait du RAG".

---

## Architecture

- **Base vectorielle** : `pgvector`, extension installée directement dans notre PostgreSQL
  existant plutôt qu'un service dédié (Chroma, Pinecone) — cohérent avec la logique de
  dimensionnement appliquée au reste du projet.
- **Embeddings** : `nomic-embed-text` via Ollama, 100% local, aucun coût, aucune donnée
  envoyée à l'extérieur (pertinent en contexte bancaire).
- **Génération** : `llama3.1:8b` via Ollama, local également.
- **Orchestration** : LangChain (LCEL — `prompt | llm | parser`).
- **Pattern de retrieval** : *Parent Document Retrieval* — recherche fine au niveau chunk
  pour identifier le bon document, puis récupération du document entier comme contexte.
- **Enrichissement du retrieval** : *Contextual Retrieval* — le titre du document enrichit
  le texte utilisé pour le calcul de l'embedding (jamais le texte stocké/affiché).
- **Garde-fou** : script de vérification de fidélité factuelle (`groundedness_check.py`) —
  détecte si les faits chiffrés du contexte (seuils, montants, délais) apparaissent bien
  dans la réponse générée.

---

## Piège 1 — Granularité du chunking

**Symptôme** : le retrieval remontait systématiquement le titre et la phrase d'introduction
d'un document, jamais les étapes détaillées contenant les chiffres importants.

**Cause racine** : le découpage se faisait uniquement sur les lignes vides (`\n\n`). Une
liste numérotée entière (5 étapes) formait donc un unique chunk très long. L'embedding
d'un chunk long et dense "dilue" son sens — il représente mal chacune des idées qu'il
contient, et se fait battre par des petits chunks courts mais sémantiquement "propres"
(comme un titre), même si ces derniers sont peu informatifs.

**Correctif** : détection des items de liste numérotée (regex `^\d+\.\s`) pour que chaque
étape devienne son propre chunk, indépendamment des lignes vides.

**Principe général** : la granularité du chunking a un impact direct sur la qualité du
retrieval, indépendamment de la qualité du modèle d'embeddings ou du LLM. Un chunking
naïf (juste sur les paragraphes) échoue souvent sur du contenu structuré (listes, tableaux).

**En entretien** : *"J'ai identifié que mon découpage initial produisait des chunks trop
longs et sémantiquement dilués sur les listes structurées — j'ai adapté le chunking pour
qu'il respecte la structure logique du document, pas seulement sa mise en forme."*

---

## Piège 2 — Conventions spécifiques au modèle d'embeddings

**Symptôme** : après correction du chunking, le retrieval restait décevant, sans erreur
visible.

**Cause racine** : `nomic-embed-text` a été entraîné avec des préfixes de tâche obligatoires
(`search_document:` pour l'indexation, `search_query:` pour la recherche). Sans eux, le
modèle produit quand même des vecteurs — aucune erreur n'est levée — mais l'espace
vectoriel n'est pas correctement aligné pour une recherche asymétrique (question courte
cherchant un passage long), ce qui dégrade silencieusement la qualité du classement.

**Correctif** : ajout systématique du bon préfixe selon le contexte d'appel (indexation vs
requête).

**Principe général** : chaque modèle d'embeddings a ses propres conventions d'usage. Les
ignorer ne provoque jamais d'erreur explicite — juste une dégradation silencieuse,
difficile à diagnostiquer sans creuser. Toujours lire la documentation du modèle
d'embeddings choisi, pas seulement celle du framework d'orchestration.

**En entretien** : *"J'ai découvert qu'un modèle d'embeddings peut avoir des conventions
d'usage propres, non génériques — les ignorer ne casse rien visiblement, mais dégrade la
qualité du retrieval sans qu'aucune erreur ne le signale."*

---

## Piège 3 — Retrieval fragmenté sur du contenu séquentiel

**Symptôme** : même avec un bon chunking et les bons préfixes, une recherche par chunk ne
remontait jamais l'intégralité d'une procédure à 5 étapes — seulement 2-3 fragments
partiels, jamais la même sélection deux fois.

**Cause racine** : une question générale ("que dois-je faire ?") ressemble sémantiquement
de façon comparable à *chaque* étape individuelle d'une procédure — aucune ne "gagne"
clairement le classement. Le retrieval par similarité chunk-à-chunk n'est pas conçu pour
garantir l'exhaustivité d'un contenu séquentiel, seulement la pertinence individuelle
de chaque fragment.

**Correctif** : pattern *Parent Document Retrieval* — la recherche vectorielle sert
uniquement à identifier le document le plus pertinent (via le meilleur score de ses
chunks), puis on fournit au LLM le document entier reconstitué, pas les chunks isolés.

**Principe général** : la granularité optimale pour la recherche (petits chunks précis)
n'est pas toujours la granularité optimale pour le contexte donné au LLM (besoin
d'exhaustivité). Découpler les deux résout ce compromis.

**En entretien** : *"J'ai appliqué le pattern Parent Document Retrieval — rechercher fin,
mais fournir large — pour garantir qu'une procédure séquentielle soit toujours restituée
dans son intégralité plutôt que fragmentée entre chunks."*

---

## Piège 4 — Arrêt prématuré de génération

**Symptôme** : le contexte envoyé au LLM contenait bien l'intégralité de la procédure
(vérifié par affichage direct), mais la réponse générée s'arrêtait après l'étape 2, sans
justification apparente.

**Fausses pistes explorées et écartées avec preuves** : d'abord soupçonné un dépassement de
la fenêtre de contexte Ollama (`num_ctx`, 2048 tokens par défaut) — corrigé en l'élargissant
à 8192, sans effet. L'inspection des métadonnées de réponse Ollama (`done_reason`,
`eval_count`) a révélé `done_reason: stop` avec seulement 285 tokens générés sur 8192
disponibles : aucune limite technique n'était en cause.

**Cause racine réelle** : le prompt système ne demandait pas explicitement l'exhaustivité
face à une liste d'étapes. Le modèle interprétait une question ouverte comme une invitation
à répondre partiellement, et générait volontairement son propre token de fin.

**Correctif** : instruction explicite et non ambiguë dans le prompt système : si le contexte
contient une liste d'étapes numérotées, les restituer TOUTES, sans exception.

**Principe général** : un arrêt de génération sans erreur technique est un problème de
prompt, pas d'infrastructure. Toujours vérifier `done_reason` avant de corriger un
paramètre technique à l'aveugle — corriger la mauvaise cause peut sembler fonctionner par
coïncidence (ou pas du tout), sans jamais adresser le vrai problème.

**En entretien** : *"Avant de conclure sur la cause d'un problème de génération, j'ai
vérifié les métadonnées techniques de la réponse (raison d'arrêt, tokens consommés)
plutôt que de corriger des paramètres au hasard — ça m'a évité de corriger un faux
problème et m'a dirigé vers la vraie cause, l'ambiguïté du prompt."*

---

## Piège 5 — Biais lexical de retrieval

**Symptôme** : sur une question mentionnant littéralement "procédure d'escalade", le
document `procedure_remboursement_client.md` (qui ne fait que *mentionner* "voir procédure
d'escalade" en passant) était classé devant le vrai document `procedure_escalade_fraude.md`.

**Cause racine** : les titres des documents (filtrés du corps du texte pour éviter le
piège n°1 — chunks peu informatifs) contenaient le vocabulaire clé absent du corps du
texte. Un document qui répète littéralement les mots de la question dans son corps peut
l'emporter, même de justesse, sur le document réellement pertinent mais formulé
différemment.

**Correctif** : *Contextual Retrieval* — le titre du document enrichit le texte utilisé
pour **calculer l'embedding** de chaque chunk, sans jamais modifier le texte stocké ou
affiché dans le contexte final. Ça redonne au modèle le signal du vocabulaire du titre
sans dupliquer ce texte ni recréer un chunk peu informatif.

**Principe général** : un retrieval sémantique n'est jamais parfaitement immunisé contre
les recoupements lexicaux fortuits. Enrichir le signal d'indexation (métadonnées, titre,
résumé) sans altérer le contenu réellement restitué est une technique reconnue pour
réduire ce risque.

**En entretien** : *"J'ai constaté qu'un document sans rapport direct pouvait devancer le
bon document à cause d'un recoupement de vocabulaire fortuit — j'ai résolu ça avec le
contextual retrieval, une technique qui enrichit le signal d'indexation sans polluer le
contenu final envoyé au modèle."*

---

## Vocabulaire à maîtriser

| Terme | Définition courte |
|---|---|
| Embedding | Représentation vectorielle numérique du sens d'un texte |
| Recherche sémantique | Recherche par similarité de sens (embeddings), pas par mot-clé |
| Distance cosinus | Mesure de similarité entre deux vecteurs (0 = identique) |
| Chunking | Découpage d'un document en fragments indexables séparément |
| Chunk | Un fragment de texte, unité de base du retrieval |
| Top-k | Nombre de résultats les plus pertinents retournés par une recherche |
| Contextual Retrieval | Enrichir l'embedding d'un chunk avec du contexte (titre, résumé) sans altérer le contenu affiché |
| Parent Document Retrieval | Rechercher fin (chunk), restituer large (document entier) |
| Groundedness / fidélité factuelle | Degré auquel une réponse générée est fondée sur le contexte fourni, pas inventée |
| Hallucination | Contenu généré par le LLM non fondé sur le contexte ou les faits |
| Temperature | Paramètre de génération contrôlant le caractère aléatoire des réponses (0 = déterministe) |
| `num_ctx` | Taille de la fenêtre de contexte d'un modèle (Ollama) |
| `done_reason` | Raison d'arrêt de génération renvoyée par Ollama (`stop` vs `length`) |
| LCEL | LangChain Expression Language — syntaxe `|` pour chaîner prompt/LLM/parser |

---

## Ce qui reste à construire

- Text-to-SQL (interrogation des données de transactions/scoring en langage naturel)
- Garde-fous de sécurité sur l'exécution SQL générée (lecture seule, validation, limite de lignes)
- Orchestrateur unifié routant entre RAG documentaire et text-to-SQL selon la question posée
