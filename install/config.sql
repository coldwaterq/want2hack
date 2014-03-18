-- Requires user postgres as logged in
DROP DATABASE IF EXISTS want2hack;
DROP ROLE IF EXISTS want2hack;
CREATE ROLE want2hack WITH PASSWORD 'want2hack' SUPERUSER;
ALTER ROLE want2hack LOGIN;
CREATE DATABASE want2hack OWNER want2hack;