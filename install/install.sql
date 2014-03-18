DROP SCHEMA IF EXISTS want2hack CASCADE;
CREATE SCHEMA want2hack;

CREATE TABLE want2hack.account  (
	user_id SERIAL PRIMARY KEY NOT NULL,
	username VARCHAR(34) UNIQUE NOT NULL,
	tagline VARCHAR(140) NULL,
	email VARCHAR(64) NOT NULL,
	description VARCHAR(400) NULL,
	avatar_filename VARCHAR(36) NULL,
	password CHAR(60),
	session_token CHAR(128) NULL,
	date_created DATE NOT NULL DEFAULT CURRENT_DATE,
	date_updated DATE NOT NULL DEFAULT CURRENT_DATE,
	date_last_session TIMESTAMP NULL,
	confirmation CHAR(64) NULL,
	attack_points INT NOT NULL DEFAULT 0,
	challenge_points INT NOT NULL DEFAULT 0
);

CREATE TABLE want2hack.challenge (
	challenge_id SERIAL PRIMARY KEY NOT NULL,
	challenge_name VARCHAR(20) NOT NULL,
	owner_id INT REFERENCES want2hack.account(user_id) NOT NULL,
	description VARCHAR(140) NOT NULL,
	flag_seed TEXT NOT NULL,
	latest_version INTEGER NOT NULL DEFAULT 1,
	latest_published_version INTEGER NULL,
	latest_approved_version INTEGER NULL,
	deleted BOOLEAN NOT NULL DEFAULT 'f',
	date_created DATE NOT NULL DEFAULT CURRENT_DATE,
	date_updated DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE want2hack.challenge_edition (
	challenge_id INT REFERENCES want2hack.challenge(challenge_id) NOT NULL,
	version INT NOT NULL DEFAULT 1,
	difficulty_estimate INT NOT NULL DEFAULT 1,
	difficulty INT NOT NULL DEFAULT 0,
	date_created DATE NOT NULL DEFAULT CURRENT_DATE,
	published BOOLEAN NOT NULL DEFAULT 'f',
	approved BOOLEAN NOT NULL DEFAULT 'f',
	PRIMARY KEY (challenge_id, version)
);

CREATE TABLE want2hack.sandbox (
	challenge_id INT REFERENCES want2hack.challenge(challenge_id) NOT NULL,
	attacker_id INT REFERENCES want2hack.account(user_id) NOT NULL,
	version_attacked INT NOT NULL,
	complete BOOLEAN NOT NULL DEFAULT 'f',
	user_points_received INT NULL,
	voted_difficulty INT NULL,
	PRIMARY KEY (challenge_id, attacker_id)
);

CREATE TABLE want2hack.messages (
	message_id SERIAL PRIMARY KEY NOT NULL,
	sender_id INT REFERENCES account(user_id) NOT NULL,
	receiver_id INT REFERENCES account(user_id) NOT NULL,
	subject VARCHAR(100) NOT NULL,
	body TEXT NOT NULL
);

CREATE TABLE want2hack.hof (
	hof_id SERIAL PRIMARY KEY NOT NULL,
	user_id INT REFERENCES want2hack.account(user_id) NOT NULL,
	user_points_received INT NOT NULL,
	description VARCHAR(140) NOT NULL
);

-- For future features

CREATE TABLE want2hack.sandbox_note (
	note_id SERIAL PRIMARY KEY NOT NULL,
	sandbox_id INT REFERENCES want2hack.sandbox(sandbox_id) NOT NULL,
	description VARCHAR(500)
);

CREATE TABLE want2hack.tag (
	tag_id SERIAL PRIMARY KEY NOT NULL,
	name VARCHAR(50)
);

CREATE TABLE want2hack.challange_tag (
	challenge_id INT REFERENCES want2hack.challenge(challenge_id) NOT NULL,
	tag_id INT REFERENCES want2hack.tag(tag_id) NOT NULL,
	PRIMARY KEY (challenge_id, tag_id)
);

CREATE TABLE want2hack.ticket (
	bug_id SERIAL PRIMARY KEY NOT NULL,
	account_id INT REFERENCES want2hack.account(user_id) NOT NULL,
	page_url VARCHAR(140) NOT NULL,
	title VARCHAR(100) NOT NULL,
	description VARCHAR(500) NULL,
	head_info TEXT
);
