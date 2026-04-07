"""Docker container memory snapshot collection.

Provides point-in-time RSS memory snapshots from running Docker containers
using the Docker SDK.  Gracefully degrades when Docker is not available.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """RSS memory reading for a single container at a point in time."""

    container_name: str
    rss_bytes: int
    timestamp: float


class DockerMemorySampler:
    """Captures point-in-time RSS memory from running Docker containers.

    Uses the Docker SDK so no shell subprocess is required.  Containers
    that are not found or are unhealthy are silently skipped so that a
    missing sidecar does not abort a scaling run.

    Example:
        sampler = DockerMemorySampler()
        before = sampler.capture(["autopilot", "driver"])
        # ... run test ...
        after = sampler.capture(["autopilot", "driver"])
        deltas = sampler.delta_bytes(before, after)
    """

    def __init__(self) -> None:
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import docker

            # Use a short read timeout so container.stats(stream=False)
            # never hangs indefinitely when cgroup stats are slow.
            self._client = docker.from_env(timeout=10)  # type: ignore[attr-defined]
        return self._client

    def capture(self, container_names: list[str]) -> dict[str, MemorySnapshot]:
        """Capture current RSS for each named container.

        Args:
            container_names: Docker container names or IDs to sample.

        Returns:
            Mapping of container_name → MemorySnapshot.
            Containers that cannot be reached are omitted without error.
        """
        result: dict[str, MemorySnapshot] = {}

        try:
            client = self._ensure_client()
        except Exception as exc:
            logger.warning("Docker unavailable for memory sampling: %s", exc)
            return result

        ts = time.time()
        for name in container_names:
            try:
                container = client.containers.get(name)
                stats = container.stats(stream=False)
                rss = int(stats.get("memory_stats", {}).get("usage", 0))
                result[name] = MemorySnapshot(
                    container_name=name,
                    rss_bytes=rss,
                    timestamp=ts,
                )
            except Exception as exc:
                logger.debug("Memory sample skipped for %s: %s", name, exc)

        return result

    @staticmethod
    def delta_bytes(
        before: dict[str, MemorySnapshot],
        after: dict[str, MemorySnapshot],
    ) -> dict[str, int]:
        """Compute RSS delta (after − before) for containers present in both snapshots.

        Args:
            before: Snapshots captured before the test phase.
            after: Snapshots captured after the test phase.

        Returns:
            Mapping of container_name → byte delta (can be negative for GC).
        """
        result: dict[str, int] = {}
        for name in set(before) & set(after):
            result[name] = after[name].rss_bytes - before[name].rss_bytes
        return result
