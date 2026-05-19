import logging
import os
import time
from typing import Optional


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
        self._container = None
        self._container_id: Optional[str] = None

    def _pull_image(self, image: str) -> None:
        try:
            self._client.images.get(image)
            logger.info("Image already cached: %s", image)
        except Exception:
            logger.info("Pulling image (this may take a few minutes): %s",
                        image)
            self._client.images.pull(image)
            logger.info("Image pulled: %s", image)

    def _start_container(self, image: str):
        container = self._client.containers.run(
            image, command="tail -f /dev/null", detach=True, remove=False,
            mem_limit="4g", working_dir="/testbed")
        for _ in range(10):
            container.reload()
            if container.status == "running":
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Container did not reach running state in time")
        return container

    def write_file(self, container_path: str, content: str) -> None:
        import io
        import tarfile

        content_bytes = content.encode("utf-8")
        tar_buffer = io.BytesIO()
        filename = os.path.basename(container_path)
        dirpath = os.path.dirname(container_path)
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            info = tarfile.TarInfo(name=filename)
            info.size = len(content_bytes)
            tar.addfile(info, io.BytesIO(content_bytes))
        tar_buffer.seek(0)
        self._container.put_archive(dirpath, tar_buffer)

    def exec_run(self, command: str, workdir: str = "/testbed") -> str:
        if self._container is None:
            raise RuntimeError("No container running. Call start() first.")
        exit_code, output = self._container.exec_run(
            ["bash", "-c", command], workdir=workdir, demux=False)
        result = output.decode("utf-8", errors="replace") if output else ""
        if exit_code and exit_code != 0:
            logger.debug("Command exited %d: %s", exit_code, command[:80])
        return result

    def _inject_eval_script(self, eval_script: str) -> None:
        self.write_file("/tmp/eval_script.sh", eval_script)
        self.exec_run("chmod + x /tmp/eval_script.sh")
        logger.debug("Eval script injected at /tmp/eval_script.sh")

    def start(self, image: str, eval_script: str) -> str:
        self._pull_image(image)
        self._container = self._start_container(image)
        self._container_id = self._container.id
        self._inject_eval_script(eval_script)
        logger.info("Container started: %s", self._container_id[:12])
        return self._container_id

    def cleanup(self) -> None:
        if self._container is None:
            return
        try:
            self._container.stop(timeout=5)
            logger.info("Container stopped: %s", self._container_id[:12])
        except Exception:
            pass
        try:
            self._container.remove(force=True)
            logger.info("Container removed: %s", self._container_id[:12])
        except Exception:
            pass
        self._container = None
        self._container_id = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()
