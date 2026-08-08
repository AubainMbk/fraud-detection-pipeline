-- Rôle dédié en lecture seule pour FraudLens (text-to-SQL).
-- Dernière ligne de défense : même si toutes les autres validations étaient
-- contournées, ce rôle est physiquement incapable d'écrire quoi que ce soit.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fraudlens_readonly') THEN
        CREATE ROLE fraudlens_readonly WITH LOGIN PASSWORD 'readonly_pwd_dev';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE fraud_db TO fraudlens_readonly;

GRANT USAGE ON SCHEMA dbt_gold TO fraudlens_readonly;
GRANT USAGE ON SCHEMA streaming TO fraudlens_readonly;

GRANT SELECT ON ALL TABLES IN SCHEMA dbt_gold TO fraudlens_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA streaming TO fraudlens_readonly;

-- S'applique aussi aux tables créées après coup (ex: futurs modèles dbt)
ALTER DEFAULT PRIVILEGES IN SCHEMA dbt_gold GRANT SELECT ON TABLES TO fraudlens_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA streaming GRANT SELECT ON TABLES TO fraudlens_readonly;