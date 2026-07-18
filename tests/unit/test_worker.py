import os
import time
from pathlib import Path

from piki.core.config import Environment, Settings
from piki.worker.main import heartbeat_is_fresh


def test_worker_health_requires_a_fresh_heartbeat(tmp_path: Path) -> None:
    heartbeat = tmp_path / "worker-ready"
    settings = Settings(
        environment=Environment.TEST,
        worker_heartbeat_path=str(heartbeat),
        worker_heartbeat_seconds=1,
    )
    assert heartbeat_is_fresh(settings) is False

    heartbeat.touch()
    assert heartbeat_is_fresh(settings) is True

    stale_time = time.time() - 10
    os.utime(heartbeat, (stale_time, stale_time))
    assert heartbeat_is_fresh(settings) is False

