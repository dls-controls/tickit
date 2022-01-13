import pytest

from tickit.devices.eiger.eiger_settings import EigerSettings, KA_Energy

# # # # # EigerStatus Tests # # # # #


@pytest.fixture
def eiger_settings() -> EigerSettings:
    return EigerSettings()


def test_eiger_settings_constructor():
    EigerSettings()


def test_eiger_settings_getitem(eiger_settings):
    value = eiger_settings["count_time"]["value"]

    assert 0.1 == value


def test_eiger_settings_get_element(eiger_settings):
    assert "Co" == eiger_settings.element


def test_eiger_settings_set_element(eiger_settings):
    eiger_settings["element"] = "Li"

    assert "Li" == eiger_settings.element
    assert KA_Energy["Li"].value == eiger_settings.photon_energy
    assert (1240 / eiger_settings.photon_energy) / 10 == eiger_settings.wavelength
    assert 0.5 * eiger_settings.photon_energy == eiger_settings.threshold_energy


def test_eiger_settings_set_photon_energy(eiger_settings):
    eiger_settings["photon_energy"] = 1000.0

    assert 1000.0 == eiger_settings.photon_energy
    assert "" == eiger_settings.element
    assert (1240 / eiger_settings.photon_energy) / 10 == eiger_settings.wavelength
    assert 0.5 * eiger_settings.photon_energy == eiger_settings.threshold_energy


def test_eiger_settings_set_wavelength(eiger_settings):
    eiger_settings["wavelength"] = 1.24

    assert 1.24 == eiger_settings.wavelength
    assert "" == eiger_settings.element
    assert 1240 / (eiger_settings.wavelength * 10) == eiger_settings.photon_energy
    assert 0.5 * eiger_settings.photon_energy == eiger_settings.threshold_energy


def test_eiger_settings_set_count_time(eiger_settings):
    eiger_settings["count_time"] = 0.2

    assert 0.2 == eiger_settings.count_time
    assert (
        eiger_settings.count_time + eiger_settings.detector_readout_time
        == eiger_settings.frame_time
    )
