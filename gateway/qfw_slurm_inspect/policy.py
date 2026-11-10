"""The site's public QPU resource names, as job_submit.lua reads them."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable


DEFAULT_RESOURCES_FILE = "/etc/openqse/qfw-slurm/resources.lua"

_LIST_RESOURCES = """
local policy = dofile(arg[1])
if type(policy) ~= "table" or type(policy.resources) ~= "table" then
	error("the policy returns no resources table")
end
for name, service_id in pairs(policy.resources) do
	io.write(tostring(name), "\\t", tostring(service_id), "\\n")
end
"""


class ResourcePolicyError(RuntimeError):
    """Raised when the site's QPU resource names cannot be read."""


def resources_file(explicit: str | None) -> str:
    """The resources policy job_submit.lua loads, unless one is named."""

    return explicit or os.environ.get(
        "QFW_SLURM_RESOURCES_FILE", DEFAULT_RESOURCES_FILE
    )


class ResourcePolicyClient:
    """Evaluate the job_submit.lua resources policy with the Lua interpreter."""

    def __init__(
        self,
        path: str,
        timeout_seconds: float = 10.0,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ):
        if timeout_seconds <= 0:
            raise ValueError("resource policy timeout must be positive")
        self.path = path
        self.timeout_seconds = timeout_seconds
        self._runner = runner or subprocess.run

    def resources(self) -> dict[str, tuple[str, ...]]:
        """The public resource names selecting each QPM service ID."""

        try:
            completed = self._runner(
                ["lua", "-", self.path],
                input=_LIST_RESOURCES,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ResourcePolicyError(
                f"cannot read QPU resource names from {self.path}: {error}"
            ) from error
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise ResourcePolicyError(
                f"cannot read QPU resource names from {self.path}: "
                f"{detail or 'no diagnostic'}"
            )
        names: dict[str, list[str]] = {}
        for line in completed.stdout.splitlines():
            name, separator, service_id = line.partition("\t")
            if not separator or not name or not service_id:
                raise ResourcePolicyError(
                    f"malformed QPU resource in {self.path}: {line!r}"
                )
            names.setdefault(service_id, []).append(name)
        return {
            service_id: tuple(sorted(resource_names))
            for service_id, resource_names in names.items()
        }
