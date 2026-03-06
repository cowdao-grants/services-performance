"""Unit tests for InstrumentedOrderbookClient."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from cow_performance.api.instrumented_client import InstrumentedOrderbookClient
from cow_performance.metrics import MetricsStore


class TestInstrumentedOrderbookClient:
    """Tests for InstrumentedOrderbookClient."""

    @pytest.fixture
    def metrics_store(self):
        """Create a metrics store fixture."""
        return MetricsStore()

    @pytest.fixture
    def client(self, metrics_store):
        """Create an instrumented client fixture."""
        return InstrumentedOrderbookClient(
            base_url="http://localhost:8080",
            metrics_store=metrics_store,
        )

    @pytest.mark.asyncio
    async def test_submit_order_records_metrics(self, client, metrics_store):
        """Test that submit_order records API metrics."""
        signed_order = {"sellToken": "0x1", "buyToken": "0x2"}
        mock_response = {"uid": "0x123"}

        with patch.object(client._client, "submit_order", new_callable=AsyncMock) as mock_submit:
            mock_submit.return_value = mock_response
            result = await client.submit_order(signed_order)

        assert result == mock_response
        metrics = metrics_store.get_api_metrics("/api/v1/orders")
        assert len(metrics) == 1
        assert metrics[0].method == "POST"
        assert metrics[0].status_code == 201
        assert metrics[0].duration > 0

    @pytest.mark.asyncio
    async def test_submit_order_records_error_metrics(self, client, metrics_store):
        """Test that failed submit_order records error metrics."""
        signed_order = {"sellToken": "0x1", "buyToken": "0x2"}

        mock_error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=400,
            message="Bad request",
        )

        with patch.object(client._client, "submit_order", new_callable=AsyncMock) as mock_submit:
            mock_submit.side_effect = mock_error

            with pytest.raises(aiohttp.ClientResponseError):
                await client.submit_order(signed_order)

        metrics = metrics_store.get_api_metrics("/api/v1/orders")
        assert len(metrics) == 1
        assert metrics[0].status_code == 400
        assert metrics[0].error_message is not None

    @pytest.mark.asyncio
    async def test_get_order_records_metrics(self, client, metrics_store):
        """Test that get_order records API metrics."""
        order_uid = "0x1234"
        mock_response = {"uid": order_uid, "status": "open"}

        with patch.object(client._client, "get_order", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await client.get_order(order_uid)

        assert result == mock_response
        metrics = metrics_store.get_api_metrics(f"/api/v1/orders/{order_uid}")
        assert len(metrics) == 1
        assert metrics[0].method == "GET"
        assert metrics[0].status_code == 200

    @pytest.mark.asyncio
    async def test_get_trades_records_metrics(self, client, metrics_store):
        """Test that get_trades records API metrics."""
        order_uid = "0x1234"
        mock_response = [{"txHash": "0xabc"}]

        with patch.object(client._client, "get_trades", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await client.get_trades(order_uid)

        assert result == mock_response
        metrics = metrics_store.get_api_metrics(f"/api/v1/orders/{order_uid}/trades")
        assert len(metrics) == 1
        assert metrics[0].method == "GET"

    @pytest.mark.asyncio
    async def test_upload_app_data_records_metrics(self, client, metrics_store):
        """Test that upload_app_data records API metrics."""
        app_data_hash = "0x1234"
        app_data_doc = {"version": "1.0.0"}
        mock_response = {}

        with patch.object(client._client, "upload_app_data", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = mock_response
            result = await client.upload_app_data(app_data_hash, app_data_doc)

        assert result == mock_response
        metrics = metrics_store.get_api_metrics(f"/api/v1/app_data/{app_data_hash}")
        assert len(metrics) == 1
        assert metrics[0].method == "PUT"
        assert metrics[0].status_code == 200

    @pytest.mark.asyncio
    async def test_get_version_records_metrics(self, client, metrics_store):
        """Test that get_version records API metrics."""
        mock_response = {"version": "1.0.0"}

        with patch.object(client._client, "get_version", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await client.get_version()

        assert result == mock_response
        metrics = metrics_store.get_api_metrics("/api/v1/version")
        assert len(metrics) == 1
        assert metrics[0].method == "GET"
        assert metrics[0].status_code == 200

    @pytest.mark.asyncio
    async def test_check_health_does_not_record_metrics(self, client, metrics_store):
        """Test that check_health does NOT record metrics."""
        with patch.object(client._client, "check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = True
            result = await client.check_health()

        assert result is True
        # No metrics should be recorded for health checks
        assert len(metrics_store.get_api_metrics()) == 0

    @pytest.mark.asyncio
    async def test_timing_precision(self, client, metrics_store):
        """Test that timing uses perf_counter for precision."""
        order_uid = "0x1234"
        mock_response = {"uid": order_uid, "status": "open"}

        async def slow_response(_uid: str):
            await asyncio.sleep(0.1)  # 100ms delay
            return mock_response

        with patch.object(client._client, "get_order", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = slow_response
            await client.get_order(order_uid)

        metrics = metrics_store.get_api_metrics()
        assert len(metrics) == 1
        # Should be at least 100ms
        assert metrics[0].duration >= 0.1
        # But not unreasonably long
        assert metrics[0].duration < 0.5

    @pytest.mark.asyncio
    async def test_payload_size_recorded(self, client, metrics_store):
        """Test that payload size is recorded correctly."""
        signed_order = {"sellToken": "0x1" * 20, "buyToken": "0x2" * 20, "amount": "1000000"}
        mock_response = {"uid": "0x123"}

        with patch.object(client._client, "submit_order", new_callable=AsyncMock) as mock_submit:
            mock_submit.return_value = mock_response
            await client.submit_order(signed_order)

        metrics = metrics_store.get_api_metrics("/api/v1/orders")
        assert len(metrics) == 1
        assert metrics[0].payload_size > 0

    @pytest.mark.asyncio
    async def test_response_size_recorded(self, client, metrics_store):
        """Test that response size is recorded correctly."""
        order_uid = "0x1234"
        mock_response = {"uid": order_uid, "status": "open", "data": "x" * 100}

        with patch.object(client._client, "get_order", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            await client.get_order(order_uid)

        metrics = metrics_store.get_api_metrics()
        assert len(metrics) == 1
        assert metrics[0].response_size > 100

    def test_base_url_property(self, client):
        """Test that base_url property works correctly."""
        assert client.base_url == "http://localhost:8080"
