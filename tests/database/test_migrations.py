"""Database migration tests using TDD approach.

These tests verify migration structure and syntax without requiring
a live PostgreSQL instance.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def get_migration_module() -> Any:
    """Load migration module dynamically."""
    migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
    spec = importlib.util.spec_from_file_location("migration", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMigrationStructure:
    """Test migration file structure and metadata."""

    def test_migration_file_exists(self) -> None:
        """Test that migration file exists."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        assert migration_path.exists(), f"Migration file not found at {migration_path}"

    def test_migration_has_revision_id(self) -> None:
        """Test that migration has revision ID."""
        module = get_migration_module()
        assert hasattr(module, "revision"), "Migration missing 'revision' attribute"
        assert module.revision == "001_create_initial_schema"

    def test_migration_has_upgrade_function(self) -> None:
        """Test that migration has upgrade function."""
        module = get_migration_module()
        assert hasattr(module, "upgrade"), "Migration missing 'upgrade' function"
        assert callable(module.upgrade), "'upgrade' is not callable"

    def test_migration_has_downgrade_function(self) -> None:
        """Test that migration has downgrade function."""
        module = get_migration_module()
        assert hasattr(module, "downgrade"), "Migration missing 'downgrade' function"
        assert callable(module.downgrade), "'downgrade' is not callable"

    def test_migration_down_revision_is_none(self) -> None:
        """Test that initial migration has no parent."""
        module = get_migration_module()
        assert module.down_revision is None, "Initial migration should have down_revision=None"


class TestMigrationContent:
    """Test migration DDL content by inspection."""

    def test_migration_file_contains_create_user_mappings(self) -> None:
        """Test that migration creates user_mappings table."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        assert "user_mappings" in content, "Migration should create user_mappings table"
        assert "wappi_chat_id" in content, "user_mappings should have wappi_chat_id column"
        assert "bitrix_deal_id" in content, "user_mappings should have bitrix_deal_id column"
        assert "bitrix_contact_id" in content, "user_mappings should have bitrix_contact_id column"
        assert "channel" in content, "user_mappings should have channel column"
        assert "phone" in content, "user_mappings should have phone column"
        assert "created_at" in content, "user_mappings should have created_at column"
        assert "updated_at" in content, "user_mappings should have updated_at column"

    def test_migration_file_contains_create_dialog_logs(self) -> None:
        """Test that migration creates dialog_logs table."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        assert "dialog_logs" in content, "Migration should create dialog_logs table"
        assert "wappi_chat_id" in content, "dialog_logs should have wappi_chat_id column"
        assert "role" in content, "dialog_logs should have role column"
        assert "message" in content, "dialog_logs should have message column"
        assert "agent_type" in content, "dialog_logs should have agent_type column"

    def test_migration_file_contains_create_analytics(self) -> None:
        """Test that migration creates analytics table."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        assert "analytics" in content, "Migration should create analytics table"
        assert "agent_type" in content, "analytics should have agent_type column"
        assert "response_time_ms" in content, "analytics should have response_time_ms column"
        assert "success" in content, "analytics should have success column"

    def test_migration_dialog_logs_no_foreign_key(self) -> None:
        """Test that dialog_logs does NOT have a FK to user_mappings."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        assert "ForeignKey" not in content, "dialog_logs should NOT have a foreign key"

    def test_migration_file_contains_indexes(self) -> None:
        """Test that migration creates required indexes."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        assert "ix_user_mappings_deal_id" in content, "Missing index on bitrix_deal_id"
        assert "ix_dialog_logs_wappi_chat_id" in content, "Missing index on wappi_chat_id"
        assert "ix_analytics_created_at" in content, "Missing index on created_at"

    def test_migration_file_contains_unique_constraint(self) -> None:
        """Test that migration has unique constraints."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        # wappi_chat_id should be UNIQUE
        assert "unique=True" in content or "UNIQUE" in content, "Missing unique constraint"

    def test_migration_file_contains_timestamps(self) -> None:
        """Test that migration includes timestamp defaults."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        assert "server_default=sa.func.now()" in content or "DEFAULT NOW()" in content, "Missing server-side timestamp defaults"

    def test_migration_file_contains_downgrade(self) -> None:
        """Test that migration has proper downgrade logic."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        assert "drop_table" in content or "DROP TABLE" in content, "Downgrade should drop tables"
        assert "analytics" in content, "Downgrade should mention analytics table"
        assert "dialog_logs" in content, "Downgrade should mention dialog_logs table"
        assert "user_mappings" in content, "Downgrade should mention user_mappings table"


class TestAlembicConfiguration:
    """Test Alembic configuration files."""

    def test_alembic_ini_exists(self) -> None:
        """Test that alembic.ini exists."""
        ini_path = Path(__file__).parent.parent.parent / "alembic.ini"
        assert ini_path.exists(), "alembic.ini not found"

    def test_alembic_ini_has_sqlalchemy_url(self) -> None:
        """Test that alembic.ini has sqlalchemy.url config."""
        ini_path = Path(__file__).parent.parent.parent / "alembic.ini"
        content = ini_path.read_text()
        assert "sqlalchemy.url" in content, "alembic.ini missing sqlalchemy.url"

    def test_alembic_env_py_exists(self) -> None:
        """Test that alembic/env.py exists."""
        env_path = Path(__file__).parent.parent.parent / "alembic" / "env.py"
        assert env_path.exists(), "alembic/env.py not found"

    def test_alembic_env_py_has_async_support(self) -> None:
        """Test that alembic/env.py has async configuration."""
        env_path = Path(__file__).parent.parent.parent / "alembic" / "env.py"
        content = env_path.read_text()
        assert "async_engine_from_config" in content or "asyncio" in content, "env.py should support async"

    def test_alembic_env_py_uses_env_variable(self) -> None:
        """Test that env.py reads POSTGRES_DSN from environment."""
        env_path = Path(__file__).parent.parent.parent / "alembic" / "env.py"
        content = env_path.read_text()
        assert "POSTGRES_DSN" in content or "getenv" in content, "env.py should read DSN from environment"

    def test_alembic_versions_directory_exists(self) -> None:
        """Test that alembic/versions directory exists."""
        versions_dir = Path(__file__).parent.parent.parent / "alembic" / "versions"
        assert versions_dir.exists(), "alembic/versions directory not found"
        assert versions_dir.is_dir(), "alembic/versions should be a directory"

    def test_alembic_has_init_file(self) -> None:
        """Test that alembic/versions has __init__.py."""
        init_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "__init__.py"
        assert init_path.exists(), "alembic/versions/__init__.py not found"


class TestMigrationSchema:
    """Test migration schema definition."""

    def test_user_mappings_column_types(self) -> None:
        """Test that user_mappings has correct column types in code."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        # Check column definitions
        assert "sa.Integer" in content, "Should use Integer for id column"
        assert "sa.String" in content, "Should use String for varchar columns"
        assert "sa.DateTime" in content, "Should use DateTime for timestamps"

    def test_analytics_is_per_request(self) -> None:
        """Test that analytics tracks per-request data, not daily aggregation."""
        migration_path = Path(__file__).parent.parent.parent / "alembic" / "versions" / "001_create_initial_schema.py"
        content = migration_path.read_text()

        assert "response_time_ms" in content, "analytics should have response_time_ms for per-request tracking"
        assert "sa.Boolean" in content, "analytics should have Boolean success column"
        assert "message_date" not in content, "analytics should NOT have message_date (not daily aggregation)"
        assert "message_count" not in content, "analytics should NOT have message_count (not daily aggregation)"
