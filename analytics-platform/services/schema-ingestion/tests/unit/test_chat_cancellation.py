"""Tests for chat cooperative cancellation and Stop generation feature."""
import threading
import uuid
from unittest.mock import MagicMock, patch

import pytest
from app.chat_sql.chat_service import ChatService, GenerationCancelled
from app.models import DataSource, TableMeta, ColumnMeta, User


@pytest.fixture
def mock_user_and_source():
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.com",
        role="ADMIN",
        is_active=True,
    )
    source = DataSource(
        id=source_id,
        tenant_id=tenant_id,
        name="Sales DB",
        type="postgres",
        status="connected",
        database_name="sales_db",
    )
    table = TableMeta(
        id=uuid.uuid4(),
        source_id=source_id,
        schema_name="public",
        table_name="orders",
        is_active=True,
    )
    col = ColumnMeta(
        id=uuid.uuid4(),
        table_id=table.id,
        column_name="id",
        data_type="integer",
        is_active=True,
    )
    table.columns = [col]
    return user, source, table


def _setup_mock_db(source, table):
    mock_db = MagicMock()
    mock_src_query = MagicMock()
    mock_src_query.filter.return_value.filter.return_value.one_or_none.return_value = source
    mock_src_query.filter.return_value.one_or_none.return_value = source

    mock_tbl_query = MagicMock()
    mock_tbl_query.options.return_value.filter.return_value.order_by.return_value.all.return_value = [table]

    def _query_side_effect(*args, **kwargs):
        if args and args[0] is DataSource:
            return mock_src_query
        return mock_tbl_query

    mock_db.query.side_effect = _query_side_effect
    return mock_db


def test_process_text_to_sql_raises_cancelled_when_event_pre_set(mock_user_and_source):
    user, source, table = mock_user_and_source
    service = ChatService()
    service.redis_client = None

    service.schema_provider = MagicMock()
    service.schema_provider.get_connected_schema.return_value = ("sales_db", "TABLE: public.orders (id integer)")
    service.llm_provider = MagicMock()
    service.sql_executor = MagicMock()

    mock_db = _setup_mock_db(source, table)

    cancel_event = threading.Event()
    cancel_event.set()  # Already cancelled

    with patch("app.chat_sql.chat_service.RetrievalService"):
        with patch("app.context_layer.engine.ContextLayerEngine.assemble_context", return_value={"formatted_text": ""}):
            with pytest.raises(GenerationCancelled):
                service.process_text_to_sql(
                    question="total orders",
                    source_id=source.id,
                    db_session=mock_db,
                    user=user,
                    cancel_event=cancel_event,
                )

    # Assert no LLM call or SQL execution was made
    service.llm_provider.generate_sql.assert_not_called()
    service.sql_executor.execute_query.assert_not_called()


def test_process_text_to_sql_cancels_before_sql_execution(mock_user_and_source):
    user, source, table = mock_user_and_source
    service = ChatService()
    service.redis_client = None

    service.schema_provider = MagicMock()
    service.schema_provider.get_connected_schema.return_value = ("sales_db", "TABLE: public.orders (id integer)")

    cancel_event = threading.Event()

    def mock_gen_sql(*args, **kwargs):
        cancel_event.set()
        return "SELECT COUNT(*) FROM orders"

    service.llm_provider = MagicMock()
    service.llm_provider.generate_sql.side_effect = mock_gen_sql
    service.llm_provider.review_sql.return_value = "SELECT COUNT(*) FROM orders"
    service.sql_validator = MagicMock()
    service.sql_validator.validate_sql.return_value = "SELECT COUNT(*) FROM orders"
    service.sql_executor = MagicMock()

    mock_db = _setup_mock_db(source, table)

    with patch("app.chat_sql.chat_service.RetrievalService"):
        with patch("app.context_layer.engine.ContextLayerEngine.assemble_context", return_value={"formatted_text": ""}):
            with pytest.raises(GenerationCancelled):
                service.process_text_to_sql(
                    question="total orders",
                    source_id=source.id,
                    db_session=mock_db,
                    user=user,
                    cancel_event=cancel_event,
                )

    # SQL executor must NOT be called because cancellation was triggered before execution
    service.sql_executor.execute_query.assert_not_called()


def test_no_assistant_message_persisted_for_cancelled_run(mock_user_and_source):
    user, source, table = mock_user_and_source
    service = ChatService()
    service.redis_client = None

    service.schema_provider = MagicMock()
    service.schema_provider.get_connected_schema.return_value = ("sales_db", "TABLE: public.orders (id integer)")
    service.llm_provider = MagicMock()
    service.sql_executor = MagicMock()

    mock_db = _setup_mock_db(source, table)

    cancel_event = threading.Event()
    cancel_event.set()

    with patch.object(service, "_persist_exchange") as mock_persist:
        with patch("app.chat_sql.chat_service.RetrievalService"):
            with patch("app.context_layer.engine.ContextLayerEngine.assemble_context", return_value={"formatted_text": ""}):
                with pytest.raises(GenerationCancelled):
                    service.process_text_to_sql(
                        question="total orders",
                        source_id=source.id,
                        db_session=mock_db,
                        user=user,
                        cancel_event=cancel_event,
                    )
                # Verify assistant exchange is never persisted
                mock_persist.assert_not_called()


def test_caller_without_cancel_event_behaves_normally(mock_user_and_source):
    user, source, table = mock_user_and_source
    service = ChatService()
    service.redis_client = None

    service.schema_provider = MagicMock()
    service.schema_provider.get_connected_schema.return_value = ("sales_db", "TABLE: public.orders (id integer)")
    service.llm_provider = MagicMock()
    service.llm_provider.generate_sql.return_value = "SELECT COUNT(*) FROM orders"
    service.llm_provider.review_sql.return_value = "SELECT COUNT(*) FROM orders"
    service.sql_validator = MagicMock()
    service.sql_validator.validate_sql.return_value = "SELECT COUNT(*) FROM orders"
    service.sql_executor = MagicMock()
    service.sql_executor.execute_query.return_value = ([{"count": 42}], 1, 10.0, ["count"], None, False)
    service.answer_synthesizer = MagicMock()
    service.answer_synthesizer.synthesize_answer.return_value = "There are 42 orders."

    mock_db = _setup_mock_db(source, table)

    with patch("app.chat_sql.chat_service.RetrievalService"):
        with patch("app.context_layer.engine.ContextLayerEngine.assemble_context", return_value={"formatted_text": ""}):
            with patch.object(service, "_persist_exchange", return_value="conv-123"):
                result = service.process_text_to_sql(
                    question="total orders",
                    source_id=source.id,
                    db_session=mock_db,
                    user=user,
                    # cancel_event is omitted / None
                )
                assert result["success"] is True
                assert result["answer"] == "There are 42 orders."
                assert result["conversation_id"] == "conv-123"


def test_stream_endpoint_ends_without_error_event_when_cancelled():
    import asyncio
    from app.api.chat_sql import generate_sql_from_question_stream, SQLQueryRequest

    async def _run():
        req = SQLQueryRequest(question="test question", source_id=uuid.uuid4())
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.tenant_id = uuid.uuid4()
        mock_user.id = uuid.uuid4()

        with patch("app.api.chat_sql.verify_user_has_source_access"):
            with patch("app.api.chat_sql.chat_service.process_text_to_sql", side_effect=GenerationCancelled("stopped")):
                resp = await generate_sql_from_question_stream(req, mock_db, mock_user)
                chunks = []
                async for chunk in resp.body_iterator:
                    chunks.append(chunk)

                full_output = "".join(chunks)
                # Must yield early meta and status events
                assert '"type": "meta"' in full_output
                assert '"type": "status"' in full_output
                # Must NOT yield an error event when cancelled
                assert '"type": "error"' not in full_output

    asyncio.run(_run())
