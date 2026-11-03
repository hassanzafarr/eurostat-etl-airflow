"""Isolated PostgreSQL schemas shared by integration tests."""

import os
import uuid

import psycopg2
import pytest
from eurostat.database import create_tables
from psycopg2 import sql


@pytest.fixture
def database():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    schema = "etl_test_" + uuid.uuid4().hex
    admin = psycopg2.connect(dsn)
    admin.autocommit = True
    with admin.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    def factory():
        return psycopg2.connect(dsn, options=f"-csearch_path={schema}")

    try:
        create_tables(factory)
        yield factory
    finally:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        admin.close()
