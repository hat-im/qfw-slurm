from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from qfw_slurm_inspect.policy import (
    DEFAULT_RESOURCES_FILE,
    ResourcePolicyClient,
    ResourcePolicyError,
    resources_file,
)


EXAMPLE = Path(__file__).parents[2] / "config" / "resources.lua.example"


def _runner(stdout, returncode=0, stderr=""):
    def run(command, **kwargs):
        assert command == ["lua", "-", "/etc/resources.lua"]
        assert kwargs["timeout"] == 2
        assert "dofile(arg[1])" in kwargs["input"]
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    return run


def test_groups_resource_names_by_service() -> None:
    client = ResourcePolicyClient("/etc/resources.lua", 2, _runner(
        "aws-sv1\tshim-aws-qpm\nnwqsim\tnwqsim-site\naws-cepheus\tshim-aws-qpm\n"
    ))

    assert client.resources() == {
        "shim-aws-qpm": ("aws-cepheus", "aws-sv1"),
        "nwqsim-site": ("nwqsim",),
    }


def test_lua_failure_names_the_policy() -> None:
    client = ResourcePolicyClient(
        "/etc/resources.lua", 2, _runner("", 1, "cannot open /etc/resources.lua")
    )

    with pytest.raises(ResourcePolicyError, match="cannot open /etc/resources.lua"):
        client.resources()


def test_missing_lua_names_the_policy() -> None:
    def run(command, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "lua")

    with pytest.raises(ResourcePolicyError, match="/etc/resources.lua"):
        ResourcePolicyClient("/etc/resources.lua", 2, run).resources()


def test_malformed_line_is_rejected() -> None:
    client = ResourcePolicyClient("/etc/resources.lua", 2, _runner("nwqsim\n"))

    with pytest.raises(ResourcePolicyError, match="malformed QPU resource"):
        client.resources()


def test_policy_file_follows_job_submit(monkeypatch) -> None:
    monkeypatch.delenv("QFW_SLURM_RESOURCES_FILE", raising=False)
    assert resources_file(None) == DEFAULT_RESOURCES_FILE
    monkeypatch.setenv("QFW_SLURM_RESOURCES_FILE", "/site/resources.lua")
    assert resources_file(None) == "/site/resources.lua"
    assert resources_file("/named.lua") == "/named.lua"


@pytest.mark.skipif(shutil.which("lua") is None, reason="lua is not installed")
def test_reads_the_example_policy() -> None:
    assert ResourcePolicyClient(str(EXAMPLE)).resources() == {
        "nwqsim-site": ("nwqsim",),
        "iqm-ornl-20q": ("ornl-iqm-20q",),
    }
