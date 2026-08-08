"""
Garde-fous de sécurité pour les requêtes SQL générées par le LLM.
Défense en profondeur : ce validateur est une couche parmi plusieurs
(voir aussi : rôle Postgres en lecture seule, timeout de requête).
Aucune de ces couches n'est censée être suffisante seule.
"""
import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {
    "dbt_gold.fct_transaction_features",
    "streaming.scored_transactions",
}
# UNION/INTERSECT/EXCEPT combinent plusieurs SELECT et restent sûrs tant que
# chaque table référencée fait partie de la liste blanche (vérifié plus bas).
ALLOWED_STATEMENT_TYPES = (exp.Select, exp.Union, exp.Intersect, exp.Except)
MAX_ROWS = 200


class UnsafeQueryError(Exception):
    """Levée quand une requête générée ne respecte pas les règles de sécurité."""


def _table_full_name(table: exp.Table) -> str:
    return f"{table.db}.{table.name}" if table.db else table.name


def validate_and_secure_sql(sql: str) -> str:
    """Valide une requête SQL générée par le LLM et la sécurise avant exécution."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except Exception as e:
        raise UnsafeQueryError(f"SQL invalide, impossible de le parser : {e}")

    if len(statements) != 1:
        raise UnsafeQueryError("Une seule requête à la fois est autorisée.")

    statement = statements[0]
    if not isinstance(statement, ALLOWED_STATEMENT_TYPES):
        raise UnsafeQueryError(
            f"Seules les requêtes en lecture (SELECT, UNION, INTERSECT, EXCEPT) "
            f"sont autorisées (reçu : {type(statement).__name__})."
        )

    referenced_tables = {_table_full_name(t) for t in statement.find_all(exp.Table)}
    disallowed = referenced_tables - ALLOWED_TABLES
    if disallowed:
        raise UnsafeQueryError(f"Table(s) non autorisée(s) : {disallowed}")

    # Enveloppe systématique dans un SELECT englobant plafonné -- plus robuste
    # qu'ajuster un LIMIT interne au cas par cas : fonctionne uniformément
    # pour un SELECT simple comme pour un UNION, sans logique conditionnelle.
    capped = exp.select("*").from_(statement.subquery()).limit(MAX_ROWS)
    return capped.sql(dialect="postgres")