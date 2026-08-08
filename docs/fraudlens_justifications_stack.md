# FraudLens - Justifications des choix technologiques


---

## 1. Stockage brut - MinIO vs AWS S3 vs Azure Blob

**Choix fait :** MinIO en local, migration vers S3 prévue pour la démo cloud.

**Pourquoi :** MinIO implémente l'API S3 à l'identique. Développer contre MinIO en local puis pointer vers S3 en prod ne demande de changer qu'une URL et des credentials - zéro réécriture de code. C'est le principe de **parité dev/prod**.

**Écosystème :** S3 (AWS), Azure Blob Storage, Google Cloud Storage - tous conceptuellement interchangeables pour du stockage objet. Le choix entre eux dépend presque toujours du cloud déjà utilisé par l'entreprise, rarement d'un critère technique.

---

## 2. Base analytique - PostgreSQL vs Snowflake vs Databricks/Spark

**Choix fait :** PostgreSQL pour Silver/Gold, à notre échelle (6,3M lignes).

**Pourquoi - argument central à maîtriser :** Spark et les entrepôts cloud (Snowflake, BigQuery, Redshift) apportent de la valeur quand une seule machine ne suffit plus (des dizaines/centaines de millions de lignes, calcul distribué nécessaire) ou quand plusieurs équipes doivent requêter en concurrence à grande échelle. Sur 6,3M lignes, PostgreSQL avec des index bien pensés reste rapide, gratuit, et beaucoup plus simple à opérer. Choisir Spark ici aurait été de la **sur-ingénierie** - un vrai reviewer technique pose justement cette question pour voir si le candidat sait dimensionner un outil à un besoin réel.

**Écosystème :**
| Outil | Rôle | Quand l'utiliser |
|---|---|---|
| PostgreSQL | Base relationnelle, transactionnelle | Volumétrie modérée, requêtes complexes, un seul serveur suffit |
| Apache Spark / Databricks | Calcul distribué sur cluster | Données trop grosses pour une machine, transformations lourdes en parallèle |
| Snowflake / BigQuery / Redshift | Entrepôt cloud analytique (OLAP) | Requêtes analytiques à très large échelle, séparation stockage/calcul, multi-équipes |

*"J'ai délibérément gardé PostgreSQL car la volumétrie ne justifiait pas Spark -  j'introduirais Spark si le volume était multiplié par 100 : partitionnement du calcul de features, lecture distribuée depuis le data lake plutôt que du chargement en RAM."*

---

## 3. Transformation SQL - scripts SQL bruts vs dbt

**Choix fait :** SQL brut au départ, migration vers dbt prévue.

**Pourquoi dbt apporte une vraie valeur :** dbt ajoute ce qu'un simple fichier `.sql` n'a pas : versioning des modèles, tests de données déclaratifs (unicité, non-nullité, valeurs attendues), documentation auto-générée, et gestion des dépendances entre transformations (comme un DAG, mais au niveau SQL). C'est devenu le standard de facto de l'industrie pour la couche transformation ("le T de ELT").

**Écosystème :** dbt s'utilise **par-dessus** un entrepôt (Postgres, Snowflake, BigQuery, Databricks) - ce n'est pas un concurrent de ces outils, mais une surcouche de gestion. C'est pour ça qu'il est cohérent de le garder même en changeant d'entrepôt plus tard.


---

## 4. Orchestration - Airflow vs Prefect/Dagster vs cron

**Choix fait :** Airflow.

**Pourquoi :** C'est l'orchestrateur le plus répandu en entreprise en France, donc le plus rentable à apprendre pour l'employabilité - même si Prefect et Dagster sont techniquement plus modernes sur certains aspects (typage, expérience développeur).

**Écosystème :**
| Outil | Positionnement |
|---|---|
| Airflow | Standard historique, écosystème très large, un peu plus verbeux |
| Dagster | Orienté "asset" plutôt que "tâche", meilleure gestion des dépendances de données |
| Prefect | Plus léger, meilleure expérience développeur, moins répandu en grande entreprise |
| cron | Suffisant pour une tâche isolée sans dépendances ni historique - pas un vrai concurrent |


---

## 5. Modèle - XGBoost vs régression logistique vs deep learning

**Choix fait :** XGBoost, comparé explicitement à une régression logistique baseline.

**Pourquoi :** Sur données tabulaires structurées (montants, ratios, catégories), les modèles à base d'arbres de gradient boosting (XGBoost, LightGBM, CatBoost) surpassent presque systématiquement le deep learning, qui excelle surtout sur données non structurées (image, texte, son). Partir d'une baseline simple (régression logistique) avant un modèle complexe est une méthodologie standard - ça permet de mesurer si la complexité ajoutée est justifiée par un vrai gain.

**Écosystème :** LightGBM et CatBoost sont les concurrents directs de XGBoost - différences de performance marginales, le choix est souvent une question d'habitude d'équipe. Les réseaux de neurones profonds (deep learning) deviennent pertinents pour la fraude quand on exploite des données séquentielles complexes (embeddings de graphes de transactions, séries temporelles longues) - hors de portée d'un premier projet.


---

## 6. Tracking de modèles - sauvegarde manuelle (`joblib`) vs MLflow

**Choix fait :** `joblib.dump()` en développement, MLflow prévu pour la suite.

**Pourquoi MLflow :** Dès qu'on entraîne plusieurs versions de modèle (changement de features, de seuil, d'hyperparamètres - ce qu'on a déjà fait plusieurs fois dans ce projet), il faut un historique structuré : quelle version a quelles métriques, avec quel seuil, entraînée sur quelles données. MLflow formalise exactement ce qu'on a fait à la main en changeant `fraud_baseline_xgb.joblib`.

**Écosystème :** MLflow est open source et cloud-agnostique. Databricks propose une version managée de MLflow intégrée nativement - c'est un des liens directs entre "MLflow" et "Databricks" dans les offres d'emploi qui listent les deux.


---

## 7. API de scoring - FastAPI vs Flask vs Django REST

**Choix fait :** FastAPI.

**Pourquoi :** Validation automatique des schémas d'entrée (Pydantic), documentation interactive générée automatiquement, support natif de l'asynchrone. C'est devenu le standard pour les APIs de services ML en 2025-2026.

**Écosystème :** Flask reste répandu (plus simple, plus de contrôle manuel, mais pas de validation native). Django REST Framework est plus lourd, pertinent surtout si l'application a aussi besoin d'un ORM complet et d'une interface d'administration - rarement le cas pour un simple service de scoring.

---

## 8. Streaming - Redpanda vs Kafka natif

**Choix fait :** Redpanda (compatible API Kafka).

**Pourquoi :** Même code client, même concepts (topics, partitions, consumer groups), mais un seul binaire au lieu de Kafka + Zookeeper - bien plus simple à opérer en local sans sacrifier la compétence recherchée par les recruteurs.

**Écosystème :** Kafka reste le standard historique et le plus présent dans les stacks existantes en entreprise (donc à connaître conceptuellement). Redpanda, Kafka géré (Confluent Cloud, AWS MSK) sont les déclinaisons modernes du même modèle.

---

## 9. La brique différenciante - RAG / LangChain (FraudLens)

**Choix fait :** Interface en langage naturel pour les analystes fraude, combinant données structurées (nos tables Gold/streaming) et documents non structurés (procédures de compliance, historiques de cas).

**Pourquoi c'est le bon différenciant :** La plupart des projets s'arrêtent au modèle ou à l'API. Une interface RAG bien construite démontre une capacité cruciale : faire dialoguer un LLM avec des données d'entreprise réelles, pas juste un chatbot générique.

**Écosystème à connaître :**
| Brique | Rôle | Alternatives |
|---|---|---|
| LangChain / LlamaIndex | Framework d'orchestration LLM (chaînage de prompts, gestion du contexte) | Écrire l'orchestration à la main (plus de contrôle, plus de code) |
| Base vectorielle (Chroma, Pgvector, Pinecone) | Stocke les embeddings des documents pour la recherche sémantique | Pgvector est intéressant ici : reste dans Postgres, pas un service en plus |
| LLM (API Anthropic/OpenAI, ou modèle open source local) | Génère la réponse en langage naturel | Modèle managé (simple, payant à l'usage) vs auto-hébergé (complexe, gratuit à l'usage) |
| Text-to-SQL | Traduit une question en langage naturel vers une requête sur nos tables Gold | Approche complémentaire au RAG documentaire pur |

**Point important à avoir en tete :** un système RAG en contexte bancaire soulève une vraie question de gouvernance - peut-on faire confiance à un LLM pour répondre sur des données sensibles ? On documentera les limites (hallucination possible, besoin de citer les sources, human-in-the-loop pour toute décision impactante) 

---

## 10. CI/CD - GitHub Actions vs GitLab CI vs Jenkins

**Choix fait :** GitHub Actions

**Pourquoi :** Intégré nativement au dépôt, pas d'infrastructure à gérer, syntaxe YAML simple. Suffisant pour un projet de cette taille (tests automatiques + build Docker à chaque push).

**Écosystème :** GitLab CI est équivalent si le dépôt est sur GitLab. Jenkins reste très présent en grande entreprise (plus ancien, plus configurable, plus lourd à maintenir) - bon à connaître conceptuellement, rarement le premier choix pour un nouveau projet aujourd'hui.

---




