import asyncio
import logging
from dataclasses import fields
from queue import Queue
from typing import Any, Iterable, Optional

from typing_extensions import TypedDict

from tickit.core.device import Device, DeviceUpdate
from tickit.core.typedefs import SimTime
from tickit.devices.eiger.data.dummy_image import Image
from tickit.devices.eiger.data.schema import fmt_json
from tickit.devices.eiger.eiger_schema import Value, construct_value
from tickit.devices.eiger.eiger_settings import EigerSettings
from tickit.devices.eiger.filewriter.filewriter_config import FileWriterConfig
from tickit.devices.eiger.filewriter.filewriter_status import FileWriterStatus
from tickit.devices.eiger.monitor.monitor_config import MonitorConfig
from tickit.devices.eiger.monitor.monitor_status import MonitorStatus
from tickit.devices.eiger.stream.stream_config import StreamConfig
from tickit.devices.eiger.stream.stream_status import StreamStatus

from .eiger_status import EigerStatus, State

LOGGER = logging.getLogger("Eiger")


class EigerDevice(Device):
    """A device class for the Eiger detector."""

    settings: EigerSettings
    status: EigerStatus

    _num_frames_left: int
    _data_queue: Queue

    #: An empty typed mapping of input values
    Inputs: TypedDict = TypedDict("Inputs", {"flux": float})
    #: A typed mapping containing the 'value' output value
    Outputs: TypedDict = TypedDict("Outputs", {})

    def __init__(
        self,
    ) -> None:
        """An Eiger device constructor.

        An Eiger device constructor which configures the default settings and various
        states of the device.
        """
        self.settings = EigerSettings()
        self.status = EigerStatus()

        self.stream_status = StreamStatus()
        self.stream_config = StreamConfig()
        self.stream_callback_period = SimTime(int(1e9))

        self.filewriter_status: FileWriterStatus = FileWriterStatus()
        self.filewriter_config: FileWriterConfig = FileWriterConfig()
        self.filewriter_callback_period = SimTime(int(1e9))

        self.monitor_status: MonitorStatus = MonitorStatus()
        self.monitor_config: MonitorConfig = MonitorConfig()
        self.monitor_callback_period = SimTime(int(1e9))

        self._num_frames_left: int = 0
        self._total_frames: int = 0
        self._data_queue: Queue = Queue()
        self._series_id: int = 0

        self._finished_aquisition: Optional[asyncio.Event] = None

    @property
    def finished_aquisition(self) -> asyncio.Event:
        """Property to instanciate an asyncio Event if it hasn't aready been."""
        if self._finished_aquisition is None:
            self._finished_aquisition = asyncio.Event()

        return self._finished_aquisition

    async def initialize(self) -> None:
        """Function to initialise the Eiger."""
        self._set_state(State.IDLE)

    async def arm(self) -> None:
        """Function to arm the Eiger."""
        self._set_state(State.READY)

        self._series_id += 1

        jsons = []

        header_detail = self.stream_config["header_detail"]["value"]

        header_json = {
            "header_detail": header_detail,
            "htype": "dheader-1.0",
            "series": self._series_id,
        }
        jsons.append(header_json)

        if header_detail != "none":
            config_json = {}
            disallowed_configs = ["flatfield", "pixelmask" "countrate_correction_table"]
            for field_ in fields(self.settings):
                if field_.name not in disallowed_configs:
                    config_json[field_.name] = vars(self.settings)[field_.name]

            jsons.append(config_json)

            if header_detail == "all":

                x = self.settings.x_pixels_in_detector
                y = self.settings.y_pixels_in_detector

                flatfield_header = {
                    "htype": "flatfield-1.0",
                    "shape": [x, y],
                    "type": "float32",
                }
                jsons.append(flatfield_header)
                flatfield_data_blob = {"blob": "blob"}
                jsons.append(flatfield_data_blob)

                pixel_mask_header = {
                    "htype": "dpixelmask-1.0",
                    "shape": [x, y],
                    "type": "uint32",
                }
                jsons.append(pixel_mask_header)
                pixel_mask_data_blob = {"blob": "blob"}
                jsons.append(pixel_mask_data_blob)

                countrate_table_header = {
                    "htype": "dcountrate_table-1.0",
                    "shape": [x, y],
                    "type": "float32",
                }
                jsons.append(countrate_table_header)
                countrate_table_data_blob = {"blob": "blob"}
                jsons.append(countrate_table_data_blob)

        # for json_ in jsons:
        self._data_queue.put([fmt_json(json_) for json_ in jsons])

    async def disarm(self) -> None:
        """Function to disarm the Eiger."""
        self._set_state(State.IDLE)

        end_json = {"htype": "dseries_end-1.0", "series": self._series_id}

        self._data_queue.put([fmt_json(end_json)])

    async def trigger(self) -> str:
        """Function to trigger the Eiger.

        If the detector is in an external trigger mode, this is disabled as
        this software command interface only works for internal triggers.
        """
        trigger_mode = self.settings.trigger_mode
        state = self.status.state

        if state == State.READY and trigger_mode == "ints":
            self._num_frames_left = self.settings.nimages
            self._set_state(State.ACQUIRE)

            self.finished_aquisition.clear()

            return "Aquiring Data from Eiger..."
        else:
            return (
                f"Ignoring trigger, state={self.status.state},"
                f"trigger_mode={trigger_mode}"
            )

    async def cancel(self) -> None:
        """Function to stop the data acquisition.

        Function to stop the data acquisition, but only after the next
        image is finished.
        """
        self._set_state(State.READY)

        end_json = {"htype": "dseries_end-1.0", "series": self._series_id}

        self._data_queue.put([fmt_json(end_json)])

    async def abort(self) -> None:
        """Function to abort the current task on the Eiger."""
        self._set_state(State.IDLE)

        end_json = {"htype": "dseries_end-1.0", "series": self._series_id}

        self._data_queue.put([fmt_json(end_json)])

    def update(self, time: SimTime, inputs: Inputs) -> DeviceUpdate[Outputs]:
        """Update function to update the Eiger.

        Args:
            time (SimTime): The simulation time in nanoseconds.
            inputs (Inputs): A TypedDict of the inputs to the Eiger device.

        Returns:
            DeviceUpdate[Outputs]:
                The produced update event which contains the value of the device
                variables.
        """
        if self.status.state == State.ACQUIRE:
            if self._num_frames_left > 0:

                frame_id = self.settings.nimages - self._num_frames_left
                LOGGER.debug(f"Frame id {frame_id}")

                aquired = Image.create_dummy_image(frame_id)

                header_json = fmt_json(
                    {
                        "frame": aquired.index,
                        "hash": aquired.hash,
                        "htype": "dimage-1.0",
                        "series": self._series_id,
                    }
                )

                x = self.settings.x_pixels_in_detector
                y = self.settings.y_pixels_in_detector

                json2 = fmt_json(
                    {
                        "encoding": aquired.encoding,
                        "htype": "dimage_d-1.0",
                        "shape": [x, y],
                        "size": len(aquired.data),
                        "type": aquired.dtype,
                    }
                )

                json3 = fmt_json(
                    {
                        "htype": "dconfig-1.0",
                        "real_time": 0,
                        "start_time": 0,
                        "stop_time": 0,
                    }
                )

                self._data_queue.put([header_json, json2, aquired.data, json3])
                self._num_frames_left -= 1
                LOGGER.debug(f"Frames left: {self._num_frames_left}")

                return DeviceUpdate(
                    self.Outputs(), SimTime(time + int(self.settings.frame_time * 1e9))
                )

            else:
                self.finished_aquisition.set()

                LOGGER.debug("Ending Series...")
                end_json = {"htype": "dseries_end-1.0", "series": self._series_id}
                self._data_queue.put([fmt_json(end_json)])

                self._set_state(State.IDLE)

        return DeviceUpdate(self.Outputs(), None)

    def consume_data(self) -> Iterable[Any]:
        """Function to work through the data queue, yielding anything queued."""
        while not self._data_queue.empty():
            yield self._data_queue.get()

    def get_state(self) -> Value:
        """Returns the current state of the Eiger.

        Returns:
            State: The state of the Eiger.
        """
        state = construct_value(self.status, "state")

        return state

    def _set_state(self, state: State):
        self.status.state = state
