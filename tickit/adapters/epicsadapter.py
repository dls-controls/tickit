import asyncio
import os
import re
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, List, Mapping, Optional

from softioc import asyncio_dispatcher, builder, softioc

from tickit.core.adapter import Adapter, RaiseInterrupt
from tickit.core.device import Device


@dataclass(frozen=True)
class InputRecord:
    """A data container representing an EPICS input record."""

    name: str
    set: Callable
    get: Callable


@dataclass
class OutputRecord:
    """A data container representing an EPICS output record."""

    name: str


class EpicsAdapter(Adapter):
    """An adapter implementation which acts as an EPICS IOC."""

    def __init__(self, ioc_name: str) -> None:
        """An EpicsAdapter constructor which stores the db_file path and the IOC name.

        Args:
            db_file (str): The path to the db_file.
            ioc_name (str): The name of the EPICS IOC.
        """
        self.ioc_name = ioc_name
        self.interrupt_records: Dict[InputRecord, Callable[[], Any]] = {}

    def link_input_on_interrupt(
        self, record: InputRecord, getter: Callable[[], Any]
    ) -> None:
        """Adds a record and a getter to the mapping of interrupting records.

        Args:
            record (InputRecord): The record to be added.
            getter (Callable[[], Any]): The getter handle.
        """
        self.interrupt_records[record] = getter

    def after_update(self) -> None:
        """Updates IOC records immediately following a device update."""
        for record, getter in self.interrupt_records.items():
            current_value = getter()
            record.set(current_value)
            print("Record {} updated to : {}".format(record.name, current_value))

    @staticmethod
    def load_records(
        db_file: Path,
        substitutions: Mapping[str, str] = {},
        remove_dtypes: bool = False,
    ):
        """Loads the records without DTYP fields."""
        with db_file.open("rb") as inp:
            with NamedTemporaryFile(suffix=".db", delete=False) as out:
                if remove_dtypes:
                    for line in inp.readlines():
                        if not re.match(rb"\s*field\s*\(\s*DTYP", line):
                            out.write(line)

        substitutions_str = ",".join(
            [f"{key}={value}" for key, value in substitutions.items()]
        )
        softioc.dbLoadDatabase(out.name, substitutions=substitutions_str)
        os.unlink(out.name)

    def build_ioc(self) -> None:
        """Builds an EPICS python soft IOC for the adapter."""
        builder.SetDeviceName(self.ioc_name)

        softioc.devIocStats(self.ioc_name)

        builder.LoadDatabase()
        event_loop = asyncio.get_event_loop()
        dispatcher = asyncio_dispatcher.AsyncioDispatcher(event_loop)
        softioc.iocInit(dispatcher)

    async def run_forever(
        self, device: Device, raise_interrupt: RaiseInterrupt
    ) -> None:
        """Runs the server continously."""
        await super().run_forever(device, raise_interrupt)
