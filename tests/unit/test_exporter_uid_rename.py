"""Tests that active_orders is decremented correctly after a temp→real UID swap."""

import time

import pytest

from cow_performance.metrics.models import OrderMetadata, OrderStatus
from cow_performance.prometheus.exporter import PrometheusExporter


class TestExporterUidRename:
    @pytest.fixture
    def exporter(self) -> PrometheusExporter:
        return PrometheusExporter(scenario="test")

    def _created_order(self, uid: str) -> OrderMetadata:
        order = OrderMetadata(
            order_uid=uid,
            owner="0xabc",
            creation_time=time.time(),
            valid_to=int(time.time()) - 1,
        )
        order.update_status(OrderStatus.CREATED)
        return order

    def test_active_count_decrements_after_uid_swap_and_expire(
        self, exporter: PrometheusExporter
    ) -> None:
        """active_orders must reach 0 after temp→real UID swap and EXPIRED status."""
        temp_uid = "0xtemp"
        real_uid = "0xreal"

        order = self._created_order(temp_uid)
        exporter._on_metric_update("order", order)
        assert temp_uid in exporter._active_orders

        exporter._on_metric_update("uid_rename", (temp_uid, real_uid))
        assert real_uid in exporter._active_orders
        assert temp_uid not in exporter._active_orders

        order.order_uid = real_uid
        order.update_status(OrderStatus.EXPIRED)
        exporter._on_metric_update("order", order)
        assert len(exporter._active_orders) == 0

    def test_active_count_decrements_after_uid_swap_and_fill(
        self, exporter: PrometheusExporter
    ) -> None:
        """active_orders must reach 0 after temp→real UID swap and FILLED status."""
        temp_uid = "0xtemp2"
        real_uid = "0xreal2"

        order = self._created_order(temp_uid)
        exporter._on_metric_update("order", order)
        exporter._on_metric_update("uid_rename", (temp_uid, real_uid))

        order.order_uid = real_uid
        order.update_status(OrderStatus.FILLED)
        exporter._on_metric_update("order", order)
        assert len(exporter._active_orders) == 0

    def test_active_count_decrements_after_uid_swap_and_failed(
        self, exporter: PrometheusExporter
    ) -> None:
        """active_orders must reach 0 after temp→real UID swap and FAILED status."""
        temp_uid = "0xtemp3"
        real_uid = "0xreal3"

        order = self._created_order(temp_uid)
        exporter._on_metric_update("order", order)
        exporter._on_metric_update("uid_rename", (temp_uid, real_uid))

        order.order_uid = real_uid
        order.update_status(OrderStatus.FAILED)
        exporter._on_metric_update("order", order)
        assert len(exporter._active_orders) == 0

    def test_rename_uid_not_in_active_orders_is_safe(self, exporter: PrometheusExporter) -> None:
        """Renaming a UID not in active_orders must not raise."""
        exporter._on_metric_update("uid_rename", ("0xghost", "0xreal"))
        assert len(exporter._active_orders) == 0

    def test_per_trader_orders_renamed_correctly(self, exporter: PrometheusExporter) -> None:
        """_orders_by_trader must contain real_uid (not temp_uid) after swap."""
        temp_uid = "0xtemp_trader"
        real_uid = "0xreal_trader"

        order = self._created_order(temp_uid)
        exporter._on_metric_update("order", order)

        exporter._on_metric_update("uid_rename", (temp_uid, real_uid))

        for order_set in exporter._orders_by_trader.values():
            assert temp_uid not in order_set
            assert real_uid in order_set
