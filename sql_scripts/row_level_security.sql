ALTER TABLE core_registration ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_own_registrations ON core_registration
    FOR SELECT
    USING (
        -- Разрешаем доступ, если email совпадает с установленным в сессии
        email = current_setting('app.session_email', true)
        OR
        -- ИЛИ пользователь является администратором
        current_setting('app.session_role', true) IN ('admin', 'staff')
    );

CREATE POLICY staff_full_access ON core_registration
    FOR ALL
    USING (
        current_setting('app.session_role', true) IN ('admin', 'staff')
    );

ALTER TABLE core_registration FORCE ROW LEVEL SECURITY;

ALTER TABLE core_event ENABLE ROW LEVEL SECURITY;

CREATE POLICY public_read_published_events ON core_event
    FOR SELECT
    USING (status = 'published' OR current_setting('app.session_role', true) IN ('admin', 'staff'));

CREATE POLICY staff_manage_events ON core_event
    FOR ALL
    USING (current_setting('app.session_role', true) IN ('admin', 'staff'));

CREATE OR REPLACE VIEW v_recent_audit_log AS
SELECT 
    id,
    table_name,
    record_id,
    action,
    changed_by,
    changed_at,
    client_ip,
    CASE 
        WHEN action = 'INSERT' THEN 'Создана запись'
        WHEN action = 'UPDATE' THEN 'Изменена запись'
        WHEN action = 'DELETE' THEN 'Удалена запись'
    END as action_description
FROM audit_log
ORDER BY changed_at DESC
LIMIT 100;

CREATE OR REPLACE VIEW v_audit_statistics AS
SELECT 
    table_name,
    action,
    COUNT(*) as operation_count,
    DATE_TRUNC('day', changed_at) as operation_date
FROM audit_log
GROUP BY table_name, action, DATE_TRUNC('day', changed_at)
ORDER BY operation_date DESC, table_name, action;

GRANT SELECT ON v_recent_audit_log TO app_readonly;
GRANT SELECT ON v_audit_statistics TO app_readonly;
