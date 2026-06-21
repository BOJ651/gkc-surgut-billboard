CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id BIGINT,
    action VARCHAR(10) CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_data JSONB,
    new_data JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    client_ip INET
);

COMMENT ON TABLE audit_log IS 'Журнал аудита всех изменений в базе данных';
COMMENT ON COLUMN audit_log.action IS 'Тип операции: INSERT, UPDATE, DELETE';
COMMENT ON COLUMN audit_log.old_data IS 'Старые значения полей (для UPDATE/DELETE)';
COMMENT ON COLUMN audit_log.new_data IS 'Новые значения полей (для INSERT/UPDATE)';

CREATE OR REPLACE FUNCTION trg_audit_changes()
RETURNS TRIGGER AS $$
DECLARE
    v_user VARCHAR(100);
    v_ip INET;
BEGIN

    v_user := current_setting('app.session_user', true);
    v_ip := current_setting('app.client_ip', true);

    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (
            table_name, 
            record_id, 
            action, 
            new_data, 
            changed_by, 
            client_ip
        )
        VALUES (
            TG_TABLE_NAME, 
            NEW.id, 
            'INSERT', 
            to_jsonb(NEW), 
            COALESCE(v_user, 'system'), 
            v_ip
        );
        RETURN NEW;
        
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (
            table_name, 
            record_id, 
            action, 
            old_data, 
            new_data, 
            changed_by, 
            client_ip
        )
        VALUES (
            TG_TABLE_NAME, 
            NEW.id, 
            'UPDATE', 
            to_jsonb(OLD), 
            to_jsonb(NEW), 
            COALESCE(v_user, 'system'), 
            v_ip
        );
        RETURN NEW;
        
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (
            table_name, 
            record_id, 
            action, 
            old_data, 
            changed_by, 
            client_ip
        )
        VALUES (
            TG_TABLE_NAME, 
            OLD.id, 
            'DELETE', 
            to_jsonb(OLD), 
            COALESCE(v_user, 'system'), 
            v_ip
        );
        RETURN OLD;
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS audit_core_event ON core_event;
CREATE TRIGGER audit_core_event
    AFTER INSERT OR UPDATE OR DELETE ON core_event
    FOR EACH ROW 
    EXECUTE FUNCTION trg_audit_changes();

DROP TRIGGER IF EXISTS audit_core_registration ON core_registration;
CREATE TRIGGER audit_core_registration
    AFTER INSERT OR UPDATE OR DELETE ON core_registration
    FOR EACH ROW 
    EXECUTE FUNCTION trg_audit_changes();

CREATE INDEX IF NOT EXISTS idx_audit_log_table_name ON audit_log(table_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_record_id ON audit_log(record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_at ON audit_log(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);

GRANT SELECT ON audit_log TO app_readonly;
GRANT ALL ON audit_log TO gkc_app;
