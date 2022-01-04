import logging
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any, List

from .eiger_schema import (
    ro_float,
    ro_str,
    rw_bool,
    rw_float,
    rw_float_grid,
    rw_int,
    rw_str,
    rw_uint_grid,
)

LOGGER = logging.getLogger(__name__)


FRAME_WIDTH: int = 4148
FRAME_HEIGHT: int = 4362


class KA_Energy(Enum):
    """Possible element K-alpha energies for samples."""

    Li: float = 54.3
    Be: float = 108.5
    B: float = 183.3
    C: float = 277.0
    N: float = 392.4
    O: float = 524.9
    F: float = 676.8
    Ne: float = 848.6
    Na: float = 1040.98
    Mg: float = 1253.6
    Al: float = 1486.7
    Si: float = 1739.98
    P: float = 2013.7
    S: float = 2307.84
    Cl: float = 2622.39
    Ar: float = 2957.7
    K: float = 3313.8
    Ca: float = 3691.68
    Sc: float = 4090.6
    Ti: float = 4510.84
    V: float = 4952.2
    Cr: float = 5414.72
    Mn: float = 5898.75
    Fe: float = 6403.84
    Co: float = 6930.32
    Ni: float = 7478.15
    Cu: float = 8047.78
    Zn: float = 8638.86


@dataclass
class EigerSettings:
    """A data container for Eiger device configuration."""

    auto_summation: bool = field(default=True, metadata=rw_bool())
    beam_center_x: float = field(default=0.0, metadata=rw_float())
    beam_center_y: float = field(default=0.0, metadata=rw_float())
    bit_depth_image: int = field(default=16, metadata=rw_int())
    bit_depth_readout: int = field(default=16, metadata=rw_int())
    chi_increment: float = field(default=0.0, metadata=rw_float())
    chi_start: float = field(default=0.0, metadata=rw_float())
    compression: str = field(
        default="bslz4", metadata=rw_str(allowed_values=["bslz4", "lz4"])
    )
    count_time: float = field(default=0.1, metadata=rw_float())
    countrate_correction_applied: bool = field(default=True, metadata=rw_bool())
    countrate_correction_count_cutoff: int = field(default=1000, metadata=rw_int())
    data_collection_date: str = field(
        default="2021-30-09T16:30:00.000-01:00", metadata=ro_str()
    )
    description: str = field(
        default="Simulated Eiger X 16M Detector", metadata=ro_str()
    )
    detector_distance: float = field(default=2.0, metadata=rw_float())
    detector_number: str = field(default="EIGERSIM001", metadata=ro_str())
    detector_readout_time: float = field(default=0.01, metadata=rw_float())
    element: str = field(
        default="Co", metadata=rw_str(allowed_values=["", *(e.name for e in KA_Energy)])
    )
    flatfield: List[List[float]] = field(
        default_factory=lambda: [[]], metadata=rw_float_grid()
    )
    flatfield_correction_applied: bool = field(default=True, metadata=rw_bool())
    frame_time: float = field(default=0.12, metadata=rw_float())
    kappa_increment: float = field(default=0.0, metadata=rw_float())
    kappa_start: float = field(default=0.0, metadata=rw_float())
    nimages: int = field(default=1, metadata=rw_int())
    ntrigger: int = field(default=1, metadata=rw_int())
    number_of_excuded_pixels: int = field(default=0, metadata=rw_int())
    omega_increment: float = field(default=0.0, metadata=rw_float())
    omega_start: float = field(default=0.0, metadata=rw_float())
    phi_increment: float = field(default=0.0, metadata=rw_float())
    phi_start: float = field(default=0.0, metadata=rw_float())
    photon_energy: float = field(default=6930.32, metadata=rw_float())
    pixel_mask: List[List[int]] = field(
        default_factory=lambda: [[]], metadata=rw_uint_grid()
    )
    pixel_mask_applied: bool = field(default=False, metadata=rw_bool())
    roi_mode: str = field(
        default="disabled", metadata=rw_str(allowed_values=["disabled", "4M"])
    )
    sensor_material: str = field(default="Silicon", metadata=ro_str())
    sensor_thickness: float = field(default=0.01, metadata=ro_float())
    software_version: str = field(default="0.1.0", metadata=ro_str())
    threshold_energy: float = field(default=4020.5, metadata=rw_float())
    trigger_mode: str = field(
        default="exts", metadata=rw_str(allowed_values=["exts", "ints", "exte", "inte"])
    )
    two_theta_increment: float = field(default=0.0, metadata=rw_float())
    two_theta_start: float = field(default=0.0, metadata=rw_float())
    wavelength: float = field(default=1.0, metadata=rw_float())
    x_pixel_size: float = field(default=0.01, metadata=ro_float())
    x_pixels_in_detector: int = field(default=FRAME_WIDTH, metadata=rw_int())
    y_pixel_size: float = field(default=0.01, metadata=ro_float())
    y_pixels_in_detector: int = field(default=FRAME_HEIGHT, metadata=rw_int())

    def __getitem__(self, key: str) -> Any:  # noqa: D105
        f = {}
        for field_ in fields(self):
            f[field_.name] = {
                "value": vars(self)[field_.name],
                "metadata": field_.metadata,
            }
        return f[key]

    def __setitem__(self, key: str, value: Any) -> None:  # noqa: D105
        self.__dict__[key] = value

        self._check_dependencies(key, value)

    def _check_dependencies(self, key, value):

        if key == "element":
            self.photon_energy = getattr(KA_Energy, value).value
            self.wavelength = (1240 / self.photon_energy) / 10  # to convert to Angstrom
            self._calc_threshold_energy()

        elif key == "photon_energy":
            self.element = ""

            hc = 1240
            self.wavelength = (hc / self.photon_energy) / 10  # to convert to Angstrom

            self._calc_threshold_energy()

        elif key == "wavelength":
            self.element = ""

            hc = 1240
            self.photon_energy = hc / (self.wavelength * 10)  # to convert from Angstrom

            self._calc_threshold_energy()

        elif key == "count_time":
            self.frame_time = self.count_time + self.detector_readout_time

    def _calc_threshold_energy(self):

        self.threshold_energy = 0.5 * self.photon_energy

        LOGGER.warning("Flatfield not recalculated.")
