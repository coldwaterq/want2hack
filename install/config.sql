-- Requires user postgres as logged in
DROP DATABASE IF EXISTS infsek;
DROP ROLE IF EXISTS infsek;
CREATE ROLE infsek WITH PASSWORD 'infsek' SUPERUSER;
ALTER ROLE infsek LOGIN;
CREATE DATABASE infsek OWNER infsek;