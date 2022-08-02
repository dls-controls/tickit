from dataclasses import dataclass
from typing import Callable, Optional, Sequence

import pytest
from mock import AsyncMock, MagicMock, patch

from tickit.adapters.interpreters.command import CommandInterpreter
from tickit.adapters.interpreters.command.command_interpreter import Command
from tickit.core.adapter import Adapter

_GET_TYPE_HINTS = (
    "tickit.adapters.interpreters.command.command_interpreter.get_type_hints"
)


@pytest.fixture
def command_interpreter():
    return CommandInterpreter()


@pytest.fixture
def TestCommand():
    @dataclass(frozen=True)
    class TestCommand:
        command: bytes

        def __call__(self, func: Callable) -> Callable:
            setattr(func, "__command__", self)
            return func

        def parse(self, data: bytes) -> Optional[Sequence[str]]:
            if data == self.command:
                return ("arg1", "arg2")
            else:
                return None

    return TestCommand


@patch(
    _GET_TYPE_HINTS,
    lambda _: {"arg1": str, "arg2": str},
)
@pytest.mark.asyncio
async def test_command_interpreter_handle_calls_func_with_args(
    command_interpreter: CommandInterpreter,
):
    test_adapter = MagicMock(
        Adapter,
        test_method=AsyncMock(
            __command__=MagicMock(
                Command,
                interrupt=False,
                parse=MagicMock(return_value=("arg1", "arg2")),
            ),
        ),
    )
    await command_interpreter.handle(test_adapter, b"\x01")
    test_adapter.test_method.assert_awaited_once_with("arg1", "arg2")


@patch(
    _GET_TYPE_HINTS,
    lambda _: {"arg1": str, "arg2": str},
)
@pytest.mark.asyncio
async def test_command_interpreter_handle_returns_iterable_reply(
    command_interpreter: CommandInterpreter,
):
    reply = AsyncMock(__aiter__=MagicMock(), __anext__=AsyncMock())
    test_adapter = MagicMock(
        Adapter,
        test_method=AsyncMock(
            __command__=MagicMock(
                Command,
                interrupt=False,
                parse=MagicMock(return_value=("arg1", "arg2")),
            ),
            return_value=reply,
        ),
    )
    assert reply == (await command_interpreter.handle(test_adapter, b"\x01"))[0]


@patch(
    _GET_TYPE_HINTS,
    lambda _: {"arg1": str, "arg2": str},
)
@pytest.mark.asyncio
async def test_command_interpreter_handle_wraps_non_iterable_reply(
    command_interpreter: CommandInterpreter,
):
    reply = MagicMock("TestReply")
    test_adapter = MagicMock(
        Adapter,
        test_method=AsyncMock(
            __command__=MagicMock(
                Command,
                interrupt=False,
                parse=MagicMock(return_value=("arg1", "arg2")),
            ),
            return_value=reply,
        ),
    )
    assert (
        reply
        == await (await command_interpreter.handle(test_adapter, b"\x01"))[0]
        .__aiter__()
        .__anext__()
    )


@patch(
    _GET_TYPE_HINTS,
    lambda _: {"arg1": str, "arg2": str},
)
@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", [True, False])
async def test_command_interpreter_handle_returns_interupt(
    command_interpreter: CommandInterpreter, interrupt: bool
):
    test_adapter = MagicMock(
        Adapter,
        test_method=AsyncMock(
            __command__=MagicMock(
                Command,
                interrupt=interrupt,
                parse=MagicMock(return_value=("arg1", "arg2")),
            ),
            return_value="DummyReply",
        ),
    )
    assert interrupt == (await command_interpreter.handle(test_adapter, b"\x01"))[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt", [True, False])
async def test_command_interpreter_handle_skips_unparsed(
    command_interpreter: CommandInterpreter, interrupt: bool
):
    test_adapter = MagicMock(
        Adapter,
        test_method=AsyncMock(
            __command__=MagicMock(
                Command, interrupt=interrupt, parse=MagicMock(return_value=None)
            ),
            return_value="DummyReply",
        ),
    )
    assert (
        b"Request does not match any known command"
        == await (
            await command_interpreter.handle(
                test_adapter, "TestCommand".encode("utf-8")
            )
        )[0]
        .__aiter__()
        .__anext__()
    )


@pytest.mark.asyncio
async def test_command_interpreter_handle_returns_message_for_no_commands(
    command_interpreter: CommandInterpreter,
):
    test_adapter = MagicMock(Adapter)
    assert (
        b"Request does not match any known command"
        == await (
            await command_interpreter.handle(
                test_adapter, "TestCommand".encode("utf-8")
            )
        )[0]
        .__aiter__()
        .__anext__()
    )
