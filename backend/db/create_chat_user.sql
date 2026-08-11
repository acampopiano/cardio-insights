-- ===========================================================
-- Usuario MySQL de SOLO LECTURA para el asistente conversacional (chat).
-- Debe ejecutarlo un administrador (root o cuenta con GRANT OPTION)
-- en el servidor donde vive la base `incc`.
--
-- Cambiá la contraseña por una fuerte y comunicásela al equipo para
-- ponerla en backend/.env (CHAT_MYSQL_PASSWORD).
-- ===========================================================

CREATE USER IF NOT EXISTS 'cardio_chat'@'%' IDENTIFIED BY 'CAMBIAR_POR_CLAVE_FUERTE';

-- Solo SELECT, y solo sobre las tablas clínicas. Sin acceso a use_* (usuarios/claves).
GRANT SELECT ON incc.flow_coordina                 TO 'cardio_chat'@'%';
GRANT SELECT ON incc.dat_cirugia                   TO 'cardio_chat'@'%';
GRANT SELECT ON incc.call_ptcamaster               TO 'cardio_chat'@'%';
GRANT SELECT ON incc.flow_procedimientocardiologia TO 'cardio_chat'@'%';
GRANT SELECT ON incc.sqlsalud_fallece              TO 'cardio_chat'@'%';

FLUSH PRIVILEGES;

-- Verificación (debe mostrar USAGE + los GRANT SELECT):
-- SHOW GRANTS FOR 'cardio_chat'@'%';
