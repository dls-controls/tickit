import subprocess
from typing import Iterable

import pytest
from click.testing import CliRunner, Result
from mock import Mock, patch

from tickit import __version__
from tickit.cli import main


def test_cli_version():
    cmd = ["tickit", "--version"]
    assert (
        subprocess.check_output(cmd).decode().strip()
        == f"tickit, version {__version__}"
    )


@pytest.fixture
def patch_logging() -> Iterable[Mock]:
    with patch("tickit.cli.logging", autospec=True) as mock:
        yield mock


@pytest.fixture
def patch_run_tickit_simulation_builder() -> Iterable[Mock]:
    with patch("tickit.cli.TickitSimulationBuilder", autospec=True) as mock:
        yield mock


def test_cli_set_logging_level(
    patch_logging: Mock,
):
    runner: CliRunner = CliRunner()
    result: Result = runner.invoke(main, args=["--log-level", "INFO"])
    assert result.exit_code == 0
    patch_logging.basicConfig.assert_called_with(level="INFO")


def test_components_command_for_one_component(
    patch_run_tickit_simulation_builder: Mock,
):
    runner: CliRunner = CliRunner()
    runner.invoke(main, args=["components", "fake_device", "path/to/fake_device.yaml"])

    patch_run_tickit_simulation_builder.assert_called_once_with(
        "path/to/fake_device.yaml",
        "kafka",
        include_schedulers=False,
        components_to_run=("fake_device",),
    )


def test_components_command_for_multiple_components(
    patch_run_tickit_simulation_builder: Mock,
):
    runner: CliRunner = CliRunner()
    runner.invoke(
        main,
        args=[
            "components",
            "fake_device_1",
            "fake_device_2",
            "path/to/fake_device.yaml",
        ],
    )

    patch_run_tickit_simulation_builder.assert_called_once_with(
        "path/to/fake_device.yaml",
        "kafka",
        include_schedulers=False,
        components_to_run=(
            "fake_device_1",
            "fake_device_2",
        ),
    )


def test_scheduler(
    patch_run_tickit_simulation_builder: Mock,
):
    runner: CliRunner = CliRunner()
    runner.invoke(main, args=["scheduler", "path/to/fake_device.yaml"])

    patch_run_tickit_simulation_builder.assert_called_once_with(
        "path/to/fake_device.yaml",
        "kafka",
        include_components=False,
    )


def test_all(
    patch_run_tickit_simulation_builder: Mock,
):
    runner: CliRunner = CliRunner()
    runner.invoke(main, args=["all", "path/to/fake_device.yaml"])

    patch_run_tickit_simulation_builder.assert_called_once_with(
        "path/to/fake_device.yaml",
        "internal",
    )
