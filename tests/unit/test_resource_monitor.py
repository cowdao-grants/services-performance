"""Unit tests for ResourceMonitor."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from cow_performance.metrics import MetricsStore
from cow_performance.monitoring.resource_monitor import (
    DEFAULT_SERVICE_PATTERNS,
    ResourceMonitor,
    ResourceMonitorConfig,
)


class TestResourceMonitorConfig:
    """Tests for ResourceMonitorConfig."""

    def test_default_service_patterns(self):
        """Test default service patterns."""
        config = ResourceMonitorConfig()
        assert "orderbook" in config.service_patterns
        assert "autopilot" in config.service_patterns
        assert "driver" in config.service_patterns
        assert "solver" in config.service_patterns
        assert "chain" in config.service_patterns

    def test_custom_patterns(self):
        """Test custom service patterns."""
        config = ResourceMonitorConfig(service_patterns=["custom-service"])
        assert config.service_patterns == ["custom-service"]

    def test_default_sample_interval(self):
        """Test default sample interval."""
        config = ResourceMonitorConfig()
        assert config.sample_interval == 5.0

    def test_custom_sample_interval(self):
        """Test custom sample interval."""
        config = ResourceMonitorConfig(sample_interval=10.0)
        assert config.sample_interval == 10.0

    def test_default_docker_url(self):
        """Test default Docker URL is None."""
        config = ResourceMonitorConfig()
        assert config.docker_url is None

    def test_custom_docker_url(self):
        """Test custom Docker URL."""
        config = ResourceMonitorConfig(docker_url="unix:///var/run/docker.sock")
        assert config.docker_url == "unix:///var/run/docker.sock"


class TestResourceMonitor:
    """Tests for ResourceMonitor."""

    @pytest.fixture
    def metrics_store(self):
        """Create a metrics store fixture."""
        return MetricsStore()

    @pytest.fixture
    def monitor(self, metrics_store):
        """Create a resource monitor fixture."""
        return ResourceMonitor(metrics_store)

    def test_calculate_cpu_percent(self, monitor):
        """Test CPU percentage calculation."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 10000000000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 900000000},
                "system_cpu_usage": 9000000000,
            },
        }

        cpu_percent = monitor._calculate_cpu_percent(stats)
        # (100M / 1000M) * 4 * 100 = 40%
        assert cpu_percent == pytest.approx(40.0, rel=0.1)

    def test_calculate_cpu_percent_no_delta(self, monitor):
        """Test CPU calculation with no delta."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000},
                "system_cpu_usage": 1000,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 1000},
                "system_cpu_usage": 1000,
            },
        }

        cpu_percent = monitor._calculate_cpu_percent(stats)
        assert cpu_percent == 0.0

    def test_calculate_cpu_percent_empty_stats(self, monitor):
        """Test CPU calculation with empty stats."""
        cpu_percent = monitor._calculate_cpu_percent({})
        assert cpu_percent == 0.0

    def test_extract_network_stats(self, monitor):
        """Test network stats extraction."""
        stats = {
            "networks": {
                "eth0": {"rx_bytes": 1000, "tx_bytes": 500},
                "eth1": {"rx_bytes": 200, "tx_bytes": 100},
            }
        }

        rx, tx = monitor._extract_network_stats(stats)
        assert rx == 1200
        assert tx == 600

    def test_extract_network_stats_empty(self, monitor):
        """Test network stats with no networks."""
        stats = {"networks": {}}
        rx, tx = monitor._extract_network_stats(stats)
        assert rx == 0
        assert tx == 0

    def test_extract_network_stats_missing(self, monitor):
        """Test network stats with missing key."""
        stats = {}
        rx, tx = monitor._extract_network_stats(stats)
        assert rx == 0
        assert tx == 0

    def test_extract_block_io_stats(self, monitor):
        """Test block I/O stats extraction."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "Read", "value": 1000},
                    {"op": "Write", "value": 500},
                    {"op": "Read", "value": 200},
                ]
            }
        }

        read, write = monitor._extract_block_io_stats(stats)
        assert read == 1200
        assert write == 500

    def test_extract_block_io_stats_empty(self, monitor):
        """Test block I/O stats with no data."""
        stats = {"blkio_stats": {}}
        read, write = monitor._extract_block_io_stats(stats)
        assert read == 0
        assert write == 0

    def test_extract_block_io_stats_none_recursive(self, monitor):
        """Test block I/O stats with None recursive."""
        stats = {"blkio_stats": {"io_service_bytes_recursive": None}}
        read, write = monitor._extract_block_io_stats(stats)
        assert read == 0
        assert write == 0

    def test_is_running_initially_false(self, monitor):
        """Test monitor is not running initially."""
        assert monitor.is_running() is False

    def test_get_monitored_containers_empty(self, monitor):
        """Test empty container list initially."""
        assert monitor.get_monitored_containers() == []

    def test_default_service_patterns_match(self):
        """Test that default patterns are correct."""
        expected = ["orderbook", "autopilot", "driver", "solver", "chain"]
        assert DEFAULT_SERVICE_PATTERNS == expected


class TestResourceMonitorIntegration:
    """Integration tests for ResourceMonitor with mocked Docker."""

    @pytest.fixture
    def mock_docker_client(self):
        """Create a mock Docker client."""
        mock_client = MagicMock()

        # Create mock containers
        mock_container = MagicMock()
        mock_container.name = "cow-perf-orderbook-1"
        mock_container.stats.return_value = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 10000000000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 900000000},
                "system_cpu_usage": 9000000000,
            },
            "memory_stats": {
                "usage": 100000000,
                "limit": 1000000000,
            },
            "networks": {
                "eth0": {"rx_bytes": 1000, "tx_bytes": 500},
            },
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "Read", "value": 1000},
                    {"op": "Write", "value": 500},
                ]
            },
        }

        mock_client.containers.list.return_value = [mock_container]

        return mock_client

    @pytest.mark.asyncio
    async def test_discover_containers(self, mock_docker_client):
        """Test container discovery."""
        store = MetricsStore()
        monitor = ResourceMonitor(store)

        with patch.object(monitor, "_get_docker_client", return_value=mock_docker_client):
            containers = monitor._discover_containers()

        assert len(containers) == 1
        assert "cow-perf-orderbook-1" in containers

    @pytest.mark.asyncio
    async def test_discover_containers_no_match(self, mock_docker_client):
        """Test container discovery with no matching patterns."""
        # Create container that doesn't match any pattern
        mock_container = MagicMock()
        mock_container.name = "unrelated-service-1"
        mock_docker_client.containers.list.return_value = [mock_container]

        store = MetricsStore()
        monitor = ResourceMonitor(store)

        with patch.object(monitor, "_get_docker_client", return_value=mock_docker_client):
            containers = monitor._discover_containers()

        assert len(containers) == 0

    @pytest.mark.asyncio
    async def test_collect_sample(self, mock_docker_client):
        """Test sample collection from container."""
        store = MetricsStore()
        monitor = ResourceMonitor(store)

        mock_container = mock_docker_client.containers.list()[0]

        with patch.object(monitor, "_get_docker_client", return_value=mock_docker_client):
            sample = await monitor._collect_sample("orderbook", mock_container)

        assert sample is not None
        assert sample.cpu_percent > 0
        assert sample.memory_bytes == 100000000
        assert sample.memory_limit_bytes == 1000000000
        assert sample.network_rx_bytes == 1000
        assert sample.network_tx_bytes == 500

    @pytest.mark.asyncio
    async def test_collect_sample_container_not_found(self, mock_docker_client):
        """Test sample collection when container not found."""
        from docker.errors import NotFound as ContainerNotFound

        store = MetricsStore()
        monitor = ResourceMonitor(store)

        mock_container = MagicMock()
        mock_container.stats.side_effect = ContainerNotFound("Container not found")

        sample = await monitor._collect_sample("missing", mock_container)
        assert sample is None

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, mock_docker_client):
        """Test start and stop lifecycle."""
        store = MetricsStore()
        config = ResourceMonitorConfig(sample_interval=0.1)
        monitor = ResourceMonitor(store, config)

        with patch.object(monitor, "_get_docker_client", return_value=mock_docker_client):
            await monitor.start()
            assert monitor.is_running() is True

            # Let it collect a few samples
            await asyncio.sleep(0.25)

            await monitor.stop()
            assert monitor.is_running() is False

        # Should have collected samples
        metrics = store.get_resource_metrics()
        assert len(metrics) > 0

    @pytest.mark.asyncio
    async def test_start_already_running(self, mock_docker_client):
        """Test starting when already running."""
        store = MetricsStore()
        config = ResourceMonitorConfig(sample_interval=0.1)
        monitor = ResourceMonitor(store, config)

        with patch.object(monitor, "_get_docker_client", return_value=mock_docker_client):
            await monitor.start()
            await monitor.start()  # Should log warning but not fail
            assert monitor.is_running() is True
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test stopping when not running."""
        store = MetricsStore()
        monitor = ResourceMonitor(store)

        # Should not fail
        await monitor.stop()
        assert monitor.is_running() is False

    @pytest.mark.asyncio
    async def test_no_containers_found(self):
        """Test behavior when no containers match patterns."""
        store = MetricsStore()
        monitor = ResourceMonitor(store)

        mock_client = MagicMock()
        mock_client.containers.list.return_value = []

        with patch.object(monitor, "_get_docker_client", return_value=mock_client):
            await monitor.start()

        # Should not be running if no containers found
        assert monitor.is_running() is False

    @pytest.mark.asyncio
    async def test_multiple_containers(self):
        """Test monitoring multiple containers."""
        store = MetricsStore()
        config = ResourceMonitorConfig(sample_interval=0.1)
        monitor = ResourceMonitor(store, config)

        mock_client = MagicMock()

        # Create multiple mock containers
        containers = []
        for name in ["cow-perf-orderbook-1", "cow-perf-autopilot-1", "cow-perf-driver-1"]:
            mock_container = MagicMock()
            mock_container.name = name
            mock_container.stats.return_value = {
                "cpu_stats": {
                    "cpu_usage": {"total_usage": 1000000000},
                    "system_cpu_usage": 10000000000,
                    "online_cpus": 4,
                },
                "precpu_stats": {
                    "cpu_usage": {"total_usage": 900000000},
                    "system_cpu_usage": 9000000000,
                },
                "memory_stats": {"usage": 100000000, "limit": 1000000000},
                "networks": {"eth0": {"rx_bytes": 1000, "tx_bytes": 500}},
                "blkio_stats": {"io_service_bytes_recursive": []},
            }
            containers.append(mock_container)

        mock_client.containers.list.return_value = containers

        with patch.object(monitor, "_get_docker_client", return_value=mock_client):
            await monitor.start()
            assert len(monitor.get_monitored_containers()) == 3
            await asyncio.sleep(0.15)
            await monitor.stop()

        metrics = store.get_resource_metrics()
        assert len(metrics) == 3

    @pytest.mark.asyncio
    async def test_custom_docker_url(self):
        """Test using custom Docker URL."""
        store = MetricsStore()
        config = ResourceMonitorConfig(docker_url="unix:///custom/docker.sock")
        monitor = ResourceMonitor(store, config)

        with patch("docker.DockerClient") as mock_docker_class:
            mock_client = MagicMock()
            mock_client.containers.list.return_value = []
            mock_docker_class.return_value = mock_client

            monitor._get_docker_client()

            mock_docker_class.assert_called_once_with(base_url="unix:///custom/docker.sock")
