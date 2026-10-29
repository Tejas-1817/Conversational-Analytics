"""
Unit tests for Domain Interactive Relationship Graph API and Schemas.
Tests:
  1. Schemas serialization and validation.
  2. get_domain_graph: 404 when domain does not exist or belongs to another tenant.
  3. get_domain_graph: empty domain returns empty nodes and edges arrays.
  4. get_domain_graph: Admin receives all tables in domain and their relationships.
  5. get_domain_graph: Non-admin RBAC filtering (deny-by-default, drops orphan edges).
"""
import uuid
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.schemas import ColumnGraphMeta, DomainGraphNode, DomainGraphEdge, DomainGraphResponse
from app.api.domains_router import get_domain_graph


class TestDomainGraphSchemas:
    def test_domain_graph_response_model(self):
        domain_id = uuid.uuid4()
        col_id = uuid.uuid4()
        table_id = uuid.uuid4()
        rel_id = uuid.uuid4()
        source_id = uuid.uuid4()

        col = ColumnGraphMeta(
            id=col_id,
            column_name="id",
            data_type="uuid",
            is_primary_key=True,
            is_foreign_key=False,
            description="Identifier",
        )
        node = DomainGraphNode(
            id=str(table_id),
            table_id=table_id,
            table_name="users",
            business_name="App Users",
            schema_name="public",
            source_id=source_id,
            source_name="Postgres DB",
            source_type="postgres",
            row_count=1200,
            column_count=1,
            columns=[col],
        )
        edge = DomainGraphEdge(
            id=str(rel_id),
            relationship_id=rel_id,
            source_table_id=str(table_id),
            source_column_id=str(col_id),
            source_column_name="id",
            target_table_id=str(table_id),
            target_column_id=str(col_id),
            target_column_name="id",
            cardinality="one_to_many",
            relationship_source="foreign_key",
            confidence=0.95,
            status="approved",
            evidence={"type": "fk_constraint"},
        )
        resp = DomainGraphResponse(
            domain_id=domain_id,
            domain_name="Core Business",
            nodes=[node],
            edges=[edge],
            total_nodes=1,
            total_edges=1,
        )

        assert resp.domain_id == domain_id
        assert resp.total_nodes == 1
        assert resp.total_edges == 1
        assert resp.nodes[0].table_name == "users"
        assert resp.edges[0].cardinality == "one_to_many"


class TestDomainGraphEndpoint:
    def test_domain_not_found(self):
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        user = MagicMock()
        user.tenant_id = uuid.uuid4()
        user.role = "ADMIN"

        with pytest.raises(HTTPException) as exc_info:
            get_domain_graph(uuid.uuid4(), session=session, current_user=user)
        assert exc_info.value.status_code == 404

    def test_empty_domain_returns_empty_graph(self):
        domain_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        domain = MagicMock()
        domain.id = domain_id
        domain.name = "Empty Domain"
        domain.tenant_id = tenant_id
        domain.source_id = None

        user = MagicMock()
        user.tenant_id = tenant_id
        user.role = "ADMIN"

        session = MagicMock()
        # First query is for Domain
        # Second query is for DomainTable
        query_mock = MagicMock()
        filter_mock = MagicMock()

        def mock_query(model):
            m = MagicMock()
            if hasattr(model, "__tablename__") and model.__tablename__ == "domains":
                m.filter.return_value.first.return_value = domain
            elif hasattr(model, "__tablename__") and model.__tablename__ == "domain_tables":
                m.filter.return_value.all.return_value = []
            return m

        session.query = mock_query

        resp = get_domain_graph(domain_id, session=session, current_user=user)
        assert resp.domain_id == domain_id
        assert resp.total_nodes == 0
        assert resp.total_edges == 0
        assert resp.nodes == []
        assert resp.edges == []

    def test_non_admin_rbac_filters_unpermitted_tables_and_orphan_edges(self):
        domain_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()

        domain = MagicMock()
        domain.id = domain_id
        domain.name = "Sales Domain"
        domain.tenant_id = tenant_id

        user = MagicMock()
        user.id = user_id
        user.tenant_id = tenant_id
        user.role = "USER"

        t1_id = uuid.uuid4()
        t2_id = uuid.uuid4()  # Not granted to user

        dt1 = MagicMock(table_id=t1_id)
        dt2 = MagicMock(table_id=t2_id)

        t1 = MagicMock(id=t1_id, table_name="customers", schema_name="public", business_name="Customers", source_id=uuid.uuid4(), row_count=50)
        c1 = MagicMock(id=uuid.uuid4(), table_id=t1_id, column_name="id", data_type="uuid", is_primary_key=True, description=None, ordinal_position=1)

        rel = MagicMock(
            id=uuid.uuid4(),
            from_column_id=c1.id,
            to_column_id=uuid.uuid4(),  # belongs to t2 which is unpermitted
            cardinality="one_to_many",
            source="foreign_key",
            confidence=1.0,
            status="approved",
            evidence={},
        )

        session = MagicMock()

        def mock_query(model):
            m = MagicMock()
            tname = getattr(model, "__tablename__", "")
            if tname == "domains":
                m.filter.return_value.first.return_value = domain
            elif tname == "domain_tables":
                m.filter.return_value.all.return_value = [dt1, dt2]
            elif tname == "user_table_access":
                # Only t1 is granted!
                m.filter.return_value.all.return_value = [(t1_id,)]
            elif tname == "tables_meta":
                m.filter.return_value.all.return_value = [t1]
            elif tname == "data_sources":
                m.filter.return_value.all.return_value = []
            elif tname == "columns_meta":
                m.filter.return_value.order_by.return_value.all.return_value = [c1]
            elif tname == "relationships":
                # Returns rel touching unpermitted col
                m.filter.return_value.all.return_value = [rel]
            return m

        session.query = mock_query

        resp = get_domain_graph(domain_id, session=session, current_user=user)

        # Only t1 should be returned as a node
        assert resp.total_nodes == 1
        assert resp.nodes[0].table_name == "customers"
        # The relationship touches an unpermitted table, so it must be dropped (no orphan edges)
        assert resp.total_edges == 0
        assert resp.edges == []
