"""
Thread-safe metrics storage for concurrent performance testing.

Provides in-memory storage with efficient lookups and bounded
time-series data using collections.deque.
"""

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from cow_performance.metrics.models import (
    APIMetrics,
    OrderMetadata,
    ResourceMetrics,
    ResourceSample,
)


@dataclass
class MetricsStoreConfig:
    """Configuration for MetricsStore."""

    # Maximum number of API metrics to retain (per endpoint)
    max_api_metrics_per_endpoint: int = 10000

    # Maximum number of resource samples to retain (per container)
    max_resource_samples_per_container: int = 1000

    # Maximum number of orders to track
    max_orders: int = 100000


class MetricsStore:
    """
    Thread-safe in-memory metrics storage.

    Supports concurrent writes from multiple traders using asyncio.Lock.
    Uses collections.deque for bounded time-series data to limit memory usage.

    Example:
        store = MetricsStore()

        # Track an order
        async with store.lock:
            store.add_order(metadata)

        # Record API call
        async with store.lock:
            store.add_api_metric(metric)

        # Get all orders
        orders = store.get_all_orders()
    """

    def __init__(self, config: MetricsStoreConfig | None = None):
        """
        Initialize the metrics store.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or MetricsStoreConfig()
        self._lock = asyncio.Lock()

        # Order metrics storage (dict for O(1) lookup by UID)
        self._orders: dict[str, OrderMetadata] = {}

        # API metrics storage (deque per endpoint for bounded storage)
        self._api_metrics: dict[str, deque[APIMetrics]] = {}

        # Resource metrics storage (ResourceMetrics per container)
        self._resource_metrics: dict[str, ResourceMetrics] = {}

        # Callbacks for metrics updates (for real-time streaming in COW-611)
        self._callbacks: list[Callable[[str, object], None]] = []

    @property
    def lock(self) -> asyncio.Lock:
        """Get the asyncio lock for thread-safe operations."""
        return self._lock

    # --- Order Methods ---

    def add_order(self, metadata: OrderMetadata) -> None:
        """
        Add or update order metadata.

        Note: Caller should acquire lock before calling this method
        for thread-safe operation.

        Args:
            metadata: The order metadata to store
        """
        if len(self._orders) >= self.config.max_orders:
            # Remove oldest order (first inserted)
            oldest_key = next(iter(self._orders))
            del self._orders[oldest_key]

        self._orders[metadata.order_uid] = metadata
        self._notify_callbacks("order", metadata)

    def get_order(self, order_uid: str) -> OrderMetadata | None:
        """
        Get order metadata by UID.

        Args:
            order_uid: The order UID to look up

        Returns:
            OrderMetadata if found, None otherwise
        """
        return self._orders.get(order_uid)

    def get_all_orders(self) -> list[OrderMetadata]:
        """
        Get all tracked orders.

        Returns:
            List of all OrderMetadata instances
        """
        return list(self._orders.values())

    def get_orders_by_status(self, status: str) -> list[OrderMetadata]:
        """
        Get orders filtered by status.

        Args:
            status: The status to filter by (e.g., "filled", "failed")

        Returns:
            List of matching OrderMetadata instances
        """
        return [o for o in self._orders.values() if o.current_status.value == status]

    def get_orders_by_owner(self, owner: str) -> list[OrderMetadata]:
        """
        Get orders filtered by owner address.

        Args:
            owner: The owner address to filter by

        Returns:
            List of matching OrderMetadata instances
        """
        return [o for o in self._orders.values() if o.owner == owner]

    def update_order_uid(self, old_uid: str, new_uid: str) -> None:
        """
        Replace a temporary UID with the real UID from API response.

        Args:
            old_uid: The temporary/pending UID
            new_uid: The real UID from the orderbook API
        """
        if old_uid in self._orders:
            order = self._orders.pop(old_uid)
            order.order_uid = new_uid
            self._orders[new_uid] = order

    # --- API Metrics Methods ---

    def add_api_metric(self, metric: APIMetrics) -> None:
        """
        Add an API metric.

        Uses deque with maxlen for bounded storage per endpoint.

        Note: Caller should acquire lock before calling this method
        for thread-safe operation.

        Args:
            metric: The API metric to store
        """
        endpoint = metric.endpoint
        if endpoint not in self._api_metrics:
            self._api_metrics[endpoint] = deque(maxlen=self.config.max_api_metrics_per_endpoint)

        self._api_metrics[endpoint].append(metric)
        self._notify_callbacks("api", metric)

    def get_api_metrics(self, endpoint: str | None = None) -> list[APIMetrics]:
        """
        Get API metrics, optionally filtered by endpoint.

        Args:
            endpoint: Optional endpoint to filter by

        Returns:
            List of APIMetrics instances
        """
        if endpoint is not None:
            return list(self._api_metrics.get(endpoint, []))

        # Return all metrics from all endpoints
        result: list[APIMetrics] = []
        for metrics in self._api_metrics.values():
            result.extend(metrics)
        return result

    def get_api_endpoints(self) -> list[str]:
        """
        Get list of endpoints that have metrics.

        Returns:
            List of endpoint strings
        """
        return list(self._api_metrics.keys())

    # --- Resource Metrics Methods ---

    def add_resource_sample(self, container_name: str, sample: ResourceSample) -> None:
        """
        Add a resource sample for a container.

        Uses deque with maxlen for bounded storage.

        Note: Caller should acquire lock before calling this method
        for thread-safe operation.

        Args:
            container_name: The container name
            sample: The resource sample to store
        """
        if container_name not in self._resource_metrics:
            self._resource_metrics[container_name] = ResourceMetrics(
                container_name=container_name,
                samples=[],
            )

        metrics = self._resource_metrics[container_name]

        # Use deque behavior: remove oldest if at limit
        if len(metrics.samples) >= self.config.max_resource_samples_per_container:
            metrics.samples.pop(0)

        metrics.add_sample(sample)
        # Pass (container_name, sample) tuple to callbacks for Prometheus exporter
        self._notify_callbacks("resource", (container_name, sample))

    def get_resource_metrics(self, container_name: str | None = None) -> dict[str, ResourceMetrics]:
        """
        Get resource metrics, optionally filtered by container.

        Args:
            container_name: Optional container to filter by

        Returns:
            Dict mapping container name to ResourceMetrics
        """
        if container_name is not None:
            if container_name in self._resource_metrics:
                return {container_name: self._resource_metrics[container_name]}
            return {}

        return dict(self._resource_metrics)

    def get_container_names(self) -> list[str]:
        """
        Get list of containers that have metrics.

        Returns:
            List of container name strings
        """
        return list(self._resource_metrics.keys())

    # --- Callback Methods (for COW-611 real-time streaming) ---

    def register_callback(self, callback: Callable[[str, object], None]) -> None:
        """
        Register a callback for metrics updates.

        Callbacks receive (metric_type, metric_object) on each update.
        This is a hook for COW-611 real-time streaming.

        Args:
            callback: Function to call on metrics updates
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[str, object], None]) -> None:
        """
        Unregister a metrics callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, metric_type: str, metric: object) -> None:
        """Notify all registered callbacks of a metrics update."""
        for callback in self._callbacks:
            try:
                callback(metric_type, metric)
            except Exception:
                # Don't let callback errors affect metrics collection
                pass

    # --- Utility Methods ---

    def clear(self) -> None:
        """
        Clear all stored metrics.

        Note: Caller should acquire lock before calling this method
        for thread-safe operation.
        """
        self._orders.clear()
        self._api_metrics.clear()
        self._resource_metrics.clear()

    def summary(self) -> dict[str, int]:
        """
        Get a summary of stored metrics counts.

        Returns:
            Dict with counts for each metric type
        """
        return {
            "orders": len(self._orders),
            "api_endpoints": len(self._api_metrics),
            "api_metrics_total": sum(len(m) for m in self._api_metrics.values()),
            "containers": len(self._resource_metrics),
            "resource_samples_total": sum(len(m.samples) for m in self._resource_metrics.values()),
        }
