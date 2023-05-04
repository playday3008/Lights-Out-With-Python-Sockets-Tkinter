#!/usr/bin/python3
# -*- coding: utf-8 -*-

# This is just making a connection to the database and setting it up

import sqlite3  # used to talk to the SQL database

# `users` table schema:
# username: max 32 characters, unique, string
# password: 128 characters, unique, sha512 hash, string
# salt: 24 characters, unique, salt for the password, string
# wins: unsigned int, default 0
# loses: unsigned int, default 0
# games_played: unsigned int, default 0


class SqlServerConnection():

    def __init__(self, database_credential: str = "application.db") -> None:
        # Connect with the database
        # check_same_thread needs to be false because it will be running on different threads.
        # Production
        self.connection = sqlite3.connect(database_credential, check_same_thread=False)
        # Testing
        # self.connection = sqlite3.connect(":memory:")
        # Drop DB
        # self.drop_db()
        # Init DB
        self.setup_db()

    def setup_db(self) -> None:
        # This will create the users and leader board table in the sql database if they dont already exists
        c = self.connection.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username VARCHAR(32) NOT NULL UNIQUE,
            password VARCHAR(128) NOT NULL UNIQUE,
            salt VARCHAR(24) NOT NULL UNIQUE,
            wins INT UNSIGNED DEFAULT 0,
            loses INT UNSIGNED DEFAULT 0,
            games_played INT UNSIGNED DEFAULT 0
        );
        """)
        self.connection.commit()

    def drop_db(self) -> None:
        # This will drop the users and leader board table in the sql database
        c = self.connection.cursor()
        c.execute("""
        DROP TABLE IF EXISTS users;
        """)
        self.connection.commit()