"""Тести для правил виявлення аномалій сенсорів."""

import pytest

from src.models.payloads import (
    AirQualityPayload,
    CarParkPayload,
    EnergyMeterPayload,
    TrafficLightPayload,
    TrafficLightState,
)
from src.sensors_edge.anomaly_rules import detect_anomaly_flags


class TestCarParkRules:
    def test_normal_occupancy_no_flags(self) -> None:
        payload = CarParkPayload(total_spots=100, occupied_spots=40, avg_stay_minutes=60.0)
        assert detect_anomaly_flags(payload) == []

    def test_overcrowded_at_threshold(self) -> None:
        payload = CarParkPayload(total_spots=100, occupied_spots=95)
        assert "overcrowded" in detect_anomaly_flags(payload)

    def test_long_stay_flag(self) -> None:
        payload = CarParkPayload(total_spots=100, occupied_spots=30, avg_stay_minutes=300.0)
        flags = detect_anomaly_flags(payload)
        assert "long_stay" in flags
        assert "overcrowded" not in flags

    def test_full_and_long_stay_together(self) -> None:
        payload = CarParkPayload(total_spots=50, occupied_spots=50, avg_stay_minutes=400.0)
        assert {"overcrowded", "long_stay"} <= set(detect_anomaly_flags(payload))


class TestTrafficLightRules:
    def test_normal_queue_no_flags(self) -> None:
        payload = TrafficLightPayload(state=TrafficLightState.GREEN, cycle_seconds=60, queue_length=3)
        assert detect_anomaly_flags(payload) == []

    def test_congested_between_thresholds(self) -> None:
        payload = TrafficLightPayload(state=TrafficLightState.RED, cycle_seconds=90, queue_length=12)
        assert detect_anomaly_flags(payload) == ["congested"]

    def test_gridlock_at_threshold(self) -> None:
        payload = TrafficLightPayload(state=TrafficLightState.RED, cycle_seconds=90, queue_length=20)
        assert detect_anomaly_flags(payload) == ["gridlock"]

    def test_signal_off_flag(self) -> None:
        payload = TrafficLightPayload(state=TrafficLightState.OFF, cycle_seconds=60, queue_length=0)
        assert "signal_off" in detect_anomaly_flags(payload)


class TestAirQualityRules:
    def test_clean_air_no_flags(self) -> None:
        payload = AirQualityPayload(
            pm2_5=8.0,
            pm10=15.0,
            no2=20.0,
            o3=50.0,
            temperature_c=20.0,
            humidity_percent=50.0,
            pressure_hpa=1013.0,
        )
        assert detect_anomaly_flags(payload) == []

    def test_unhealthy_pm25(self) -> None:
        payload = AirQualityPayload(
            pm2_5=40.0,
            pm10=30.0,
            no2=20.0,
            o3=50.0,
            temperature_c=20.0,
            humidity_percent=50.0,
            pressure_hpa=1013.0,
        )
        assert "unhealthy_pm25" in detect_anomaly_flags(payload)

    def test_very_unhealthy_pm25(self) -> None:
        payload = AirQualityPayload(
            pm2_5=60.0,
            pm10=30.0,
            no2=20.0,
            o3=50.0,
            temperature_c=20.0,
            humidity_percent=50.0,
            pressure_hpa=1013.0,
        )
        assert "very_unhealthy_pm25" in detect_anomaly_flags(payload)

    def test_hazardous_pm25_beats_lower_levels(self) -> None:
        payload = AirQualityPayload(
            pm2_5=200.0,
            pm10=30.0,
            no2=20.0,
            o3=50.0,
            temperature_c=20.0,
            humidity_percent=50.0,
            pressure_hpa=1013.0,
        )
        flags = detect_anomaly_flags(payload)
        assert "hazardous_pm25" in flags
        assert "very_unhealthy_pm25" not in flags
        assert "unhealthy_pm25" not in flags

    def test_high_no2_and_o3_use_updated_thresholds(self) -> None:
        payload = AirQualityPayload(
            pm2_5=5.0,
            pm10=10.0,
            no2=60.0,
            o3=100.0,
            temperature_c=20.0,
            humidity_percent=50.0,
            pressure_hpa=1013.0,
        )
        flags = detect_anomaly_flags(payload)
        assert "high_no2" in flags
        assert "high_o3" in flags


class TestEnergyMeterRules:
    def test_normal_operation(self) -> None:
        payload = EnergyMeterPayload(
            power_kw=3.0,
            voltage_v=230.0,
            current_a=13.0,
            cumulative_kwh=100.0,
            power_factor=0.95,
        )
        assert detect_anomaly_flags(payload) == []

    def test_voltage_out_of_range_low(self) -> None:
        payload = EnergyMeterPayload(
            power_kw=3.0,
            voltage_v=200.0,
            current_a=13.0,
            cumulative_kwh=100.0,
            power_factor=0.95,
        )
        assert "voltage_out_of_range" in detect_anomaly_flags(payload)

    def test_voltage_out_of_range_high(self) -> None:
        payload = EnergyMeterPayload(
            power_kw=3.0,
            voltage_v=260.0,
            current_a=13.0,
            cumulative_kwh=100.0,
            power_factor=0.95,
        )
        assert "voltage_out_of_range" in detect_anomaly_flags(payload)

    def test_poor_power_factor(self) -> None:
        payload = EnergyMeterPayload(
            power_kw=3.0,
            voltage_v=230.0,
            current_a=13.0,
            cumulative_kwh=100.0,
            power_factor=0.89,
        )
        assert "poor_power_factor" in detect_anomaly_flags(payload)

    def test_none_power_factor_not_flagged(self) -> None:
        payload = EnergyMeterPayload(
            power_kw=3.0,
            voltage_v=230.0,
            current_a=13.0,
            cumulative_kwh=100.0,
            power_factor=None,
        )
        assert "poor_power_factor" not in detect_anomaly_flags(payload)

    def test_overload(self) -> None:
        payload = EnergyMeterPayload(
            power_kw=6.0,
            voltage_v=230.0,
            current_a=26.1,
            cumulative_kwh=100.0,
            power_factor=0.95,
        )
        assert "power_overload" in detect_anomaly_flags(payload)


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        (CarParkPayload(total_spots=10, occupied_spots=2), list),
        (TrafficLightPayload(state=TrafficLightState.GREEN, cycle_seconds=60, queue_length=0), list),
    ],
)
def test_detect_returns_list_type(
    payload: CarParkPayload | TrafficLightPayload,
    expected_type: type[list[str]],
) -> None:
    assert isinstance(detect_anomaly_flags(payload), expected_type)
