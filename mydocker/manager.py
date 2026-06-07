import logging
import time
from typing import Any, Optional

from mcp_servers.shared_tools._docker import _write_file_to_container


logger = logging.getLogger(__name__)


class DockerManager:
    def __init__(self) -> None:
        try:
            import docker
            self._client = docker.from_env()
        except Exception as exc:
            raise RuntimeError(
                "Docker SDK not available or Docker daemon not running."
                f"Install with: uv add docker\nError: {exc}")
        self._container: Any = None
        self._container_id: Optional[str] = None

    def _pull_image(self, image: str) -> None:
        import docker.errors
        try:
            self._client.images.get(image)
            logger.info("Image already cached: %s", image)
        except docker.errors.ImageNotFound:
            logger.info("Pulling image (this may take a few minutes): %s",
                        image)
            try:
                self._client.images.pull(image)
            except docker.errors.ImageNotFound as exc:
                raise RuntimeError(
                    f"Failed to pull Docker image '{image}'. "
                    "Ensure the image exists on Docker Hub and that your "
                    "network/Docker daemon is configured correctly.\n"
                    f"Original error: {exc}"
                ) from exc
            logger.info("Image pulled: %s", image)

    def _start_container(self, image: str) -> Any:
        import docker.errors
        kwargs: dict[str, Any] = dict(
            command=[],  # clear image CMD so it isn't appended to our entrypoint
            entrypoint=["tail", "-f", "/dev/null"],
            detach=True, remove=False,
            working_dir="/testbed", privileged=True,
            platform="linux/amd64",
        )
        try:
            container = self._client.containers.run(image, mem_limit="4g",
                                                    **kwargs)
        except docker.errors.APIError as exc:
            if "memory" in str(exc).lower():
                # Rootless Docker without cgroup memory controller — retry
                # without the memory limit rather than failing hard.
                logger.warning("mem_limit unsupported, retrying without it: %s",
                               exc)
                container = self._client.containers.run(image, **kwargs)
            else:
                raise
        for _ in range(10):
            container.reload()
            if container.status == "running":
                break
            time.sleep(0.5)
        else:
            logs = ""
            try:
                logs = container.logs().decode("utf-8", errors="replace")[-500:]
            except Exception:
                pass
            raise RuntimeError(
                f"Container did not reach running state in time "
                f"(status={container.status}). Last logs:\n{logs}"
            )
        return container

    def write_file(self, container_path: str, content: str) -> None:
        _write_file_to_container(self._container, container_path, content)

    def exec_run(self, command: str, workdir: str = "/testbed") -> str:
        if self._container is None:
            raise RuntimeError("No container running. Call start() first.")
        result = self._container.exec_run(["bash", "-c", command],
                                          workdir=workdir, demux=False)
        output = result.output or b""
        if result.exit_code and result.exit_code != 0:
            logger.debug("Command exited %d: %s", result.exit_code,
                         command[:80])
        return output.decode("utf-8", errors="replace")

    def _inject_eval_script(self, eval_script: str) -> None:
        self.write_file("/tmp/eval_script.sh", eval_script)
        self.exec_run("chmod +x /tmp/eval_script.sh")
        logger.debug("Eval script injected at /tmp/eval_script.sh")

    def start(self, image: str, eval_script: str) -> str:
        self._pull_image(image)
        self._container = self._start_container(image)
        self._container_id = str(self._container.id)
        self._inject_eval_script(eval_script)
        logger.info("Container started: %s", (self._container_id or "")[:12])
        return self._container_id

    def cleanup(self) -> None:
        if self._container is None:
            return
        try:
            self._container.stop(timeout=5)
            logger.info("Container stopped: %s", (self._container_id or "")[:12])
        except Exception:
            pass
        try:
            self._container.remove(force=True)
            logger.info("Container removed: %s", (self._container_id or "")[:12])
        except Exception:
            pass
        self._container = None
        self._container_id = None

    def __enter__(self) -> "DockerManager":
        return self

    def __exit__(self, *args: Any) -> None:
        self.cleanup()
