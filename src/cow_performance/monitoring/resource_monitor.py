"""
Docker container resource monitoring.

Collects CPU, memory, network, and I/O metrics from Docker containers
for performance analysis during load testing.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from docker.errors import NotFound as ContainerNotFound
from docker.models.containers import Container

import docker
from cow_performance.metrics import MetricsStore, ResourceSample

logger = logging.getLogger(__name__)


# Default CoW Protocol services to monitor
DEFAULT_SERVICE_PATTERNS = [
    "orderbook",
    "autopilot",
    "driver",
    "solver",  # Matches all solver types (baseline, quasimodo, etc.)
    "chain",
]


@dataclass
class ResourceMonitorConfig:
    """Configuration for ResourceMonitor."""

    # Service name patterns to match containers
    service_patterns: list[str] = field(default_factory=lambda: DEFAULT_SERVICE_PATTERNS.copy())

    # Sampling interval in seconds
    sample_interval: float = 5.0

    # Docker socket URL (None for default)
    docker_url: str | None = None


class ResourceMonitor:
    """
    Monitors Docker container resource utilization.

    Collects CPU, memory, network I/O, and block I/O metrics from containers
    matching configured service patterns and stores them in MetricsStore.

    Example:
        store = MetricsStore()
        monitor = ResourceMonitor(store)
        await monitor.start()
        # ... run tests ...
        await monitor.stop()
    """

    def __init__(
        self,
        metrics_store: MetricsStore,
        config: ResourceMonitorConfig | None = None,
    ):
        """
        Initialize the resource monitor.

        Args:
            metrics_store: Store for recording resource metrics
            config: Optional configuration (uses defaults if not provided)
        """
        self._metrics_store = metrics_store
        self._config = config or ResourceMonitorConfig()
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._docker_client: Any = None  # docker.DockerClient
        self._containers: dict[str, Container] = {}

    def _get_docker_client(self) -> Any:
        """Get or create Docker client."""
        if self._docker_client is None:
            if self._config.docker_url:
                self._docker_client = docker.DockerClient(base_url=self._config.docker_url)  # type: ignore[attr-defined]
            else:
                self._docker_client = docker.from_env()  # type: ignore[attr-defined]
        return self._docker_client

    def _discover_containers(self) -> dict[str, Container]:
        """
        Discover containers matching service patterns.

        Returns:
            Dict mapping container names to Container objects
        """
        client = self._get_docker_client()
        containers: dict[str, Container] = {}

        for container in client.containers.list():
            name = container.name
            # Check if container name matches any service pattern
            for pattern in self._config.service_patterns:
                if pattern in name:
                    containers[name] = container
                    logger.debug(f"Discovered container: {name} (matched pattern: {pattern})")
                    break

        return containers

    def _calculate_cpu_percent(self, stats: dict) -> float:
        """
        Calculate CPU percentage from Docker stats.

        Uses the same formula as `docker stats` command.

        Args:
            stats: Docker container stats dict

        Returns:
            CPU usage percentage (0-100+, can exceed 100% with multiple cores)
        """
        try:
            cpu_stats = stats.get("cpu_stats", {})
            precpu_stats = stats.get("precpu_stats", {})

            # Get CPU deltas
            cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - precpu_stats.get(
                "cpu_usage", {}
            ).get("total_usage", 0)
            system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get(
                "system_cpu_usage", 0
            )

            if system_delta > 0 and cpu_delta > 0:
                # Number of CPUs
                num_cpus = cpu_stats.get("online_cpus", 1)
                if num_cpus == 0:
                    num_cpus = len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", [1]))

                return float((cpu_delta / system_delta) * num_cpus * 100.0)

            return 0.0
        except (KeyError, TypeError, ZeroDivisionError):
            return 0.0

    def _extract_network_stats(self, stats: dict) -> tuple[int, int]:
        """
        Extract network I/O from Docker stats.

        Args:
            stats: Docker container stats dict

        Returns:
            Tuple of (rx_bytes, tx_bytes)
        """
        try:
            networks = stats.get("networks", {})
            rx_bytes = 0
            tx_bytes = 0

            for _, network_stats in networks.items():
                rx_bytes += network_stats.get("rx_bytes", 0)
                tx_bytes += network_stats.get("tx_bytes", 0)

            return rx_bytes, tx_bytes
        except (KeyError, TypeError):
            return 0, 0

    def _extract_block_io_stats(self, stats: dict) -> tuple[int, int]:
        """
        Extract block I/O from Docker stats.

        Args:
            stats: Docker container stats dict

        Returns:
            Tuple of (read_bytes, write_bytes)
        """
        try:
            blkio_stats = stats.get("blkio_stats", {})
            io_service_bytes = blkio_stats.get("io_service_bytes_recursive", []) or []

            read_bytes = 0
            write_bytes = 0

            for entry in io_service_bytes:
                op = entry.get("op", "").lower()
                value = entry.get("value", 0)
                if op == "read":
                    read_bytes += value
                elif op == "write":
                    write_bytes += value

            return read_bytes, write_bytes
        except (KeyError, TypeError):
            return 0, 0

    def _collect_sample_sync(
        self, container_name: str, container: Container
    ) -> ResourceSample | None:
        """
        Collect a single resource sample from a container (synchronous).

        Runs blocking Docker API calls that must not be called directly from
        the asyncio event loop — use _collect_sample() instead.

        Args:
            container_name: Name of the container
            container: Docker Container object

        Returns:
            ResourceSample if successful, None if collection failed
        """
        try:
            # Get stats (non-streaming for single snapshot)
            stats = container.stats(stream=False)

            # Extract metrics
            cpu_percent = self._calculate_cpu_percent(stats)

            memory_stats = stats.get("memory_stats", {})
            memory_bytes = memory_stats.get("usage", 0)
            memory_limit = memory_stats.get("limit", 0)

            rx_bytes, tx_bytes = self._extract_network_stats(stats)
            read_bytes, write_bytes = self._extract_block_io_stats(stats)

            # Get disk usage from container size
            # Use Docker's containers/json API endpoint with size parameter
            disk_usage = 0
            try:
                # The size info is only available via the containers list endpoint with size=true
                client = self._get_docker_client()
                containers_data = client.api.containers(filters={"id": container.id}, size=True)
                if containers_data:
                    # SizeRw is the writable layer size
                    disk_usage = containers_data[0].get("SizeRw", 0)
            except Exception as e:
                logger.debug(f"Failed to get disk usage for {container_name}: {e}")

            return ResourceSample(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_bytes=memory_bytes,
                memory_limit_bytes=memory_limit,
                network_rx_bytes=rx_bytes,
                network_tx_bytes=tx_bytes,
                block_read_bytes=read_bytes,
                block_write_bytes=write_bytes,
                disk_usage_bytes=disk_usage,
            )
        except ContainerNotFound:
            logger.warning(f"Container {container_name} not found, removing from monitoring")
            return None
        except Exception as e:
            logger.warning(f"Failed to collect stats from {container_name}: {e}")
            return None

    async def _collect_sample(
        self, container_name: str, container: Container
    ) -> ResourceSample | None:
        """
        Collect a single resource sample from a container.

        Runs the blocking Docker API calls in a thread executor so the
        asyncio event loop is not blocked.

        Args:
            container_name: Name of the container
            container: Docker Container object

        Returns:
            ResourceSample if successful, None if collection failed
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._collect_sample_sync, container_name, container
        )

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that collects samples at configured intervals."""
        logger.info(
            f"Starting resource monitoring with {len(self._containers)} containers, "
            f"interval={self._config.sample_interval}s"
        )

        while self._running:
            # Refresh container list periodically (containers may restart)
            loop = asyncio.get_event_loop()
            self._containers = await loop.run_in_executor(None, self._discover_containers)

            # Collect samples from all containers
            for container_name, container in list(self._containers.items()):
                sample = await self._collect_sample(container_name, container)

                if sample is not None:
                    async with self._metrics_store.lock:
                        self._metrics_store.add_resource_sample(container_name, sample)
                else:
                    # Remove container from monitoring if collection failed
                    self._containers.pop(container_name, None)

            # Wait for next sample interval
            await asyncio.sleep(self._config.sample_interval)

    async def start(self) -> None:
        """
        Start the resource monitor.

        Discovers containers and begins collecting samples in the background.
        """
        if self._running:
            logger.warning("ResourceMonitor is already running")
            return

        # Discover containers
        self._containers = self._discover_containers()
        logger.info(
            f"Discovered {len(self._containers)} containers to monitor: "
            f"{list(self._containers.keys())}"
        )

        if not self._containers:
            logger.warning(
                f"No containers found matching patterns: {self._config.service_patterns}. "
                "Resource monitoring will be disabled."
            )
            return

        # Start monitoring loop
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())

    async def stop(self) -> None:
        """Stop the resource monitor gracefully."""
        if not self._running:
            return

        logger.info("Stopping resource monitor...")
        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Clean up Docker client
        if self._docker_client:
            self._docker_client.close()
            self._docker_client = None

        self._containers.clear()
        logger.info("Resource monitor stopped")

    def is_running(self) -> bool:
        """Check if the monitor is currently running."""
        return self._running

    def get_monitored_containers(self) -> list[str]:
        """Get list of currently monitored container names."""
        return list(self._containers.keys())
