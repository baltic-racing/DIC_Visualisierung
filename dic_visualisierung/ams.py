"""Reviewed AMS TY26 sender subset, not execution of the STM32 AMS firmware.

Values are wire integers. Temperature is millidegrees Celsius. A fixed hottest
cell is assumed; LTC multiplexing, sensor conversion and SDC are not emulated.
Only the optional overtemperature rule is generated here. Manual fault bits,
explicit CAN events and raw overrides remain available for other fault tests.
"""

MAX_TEMPERATURE = 58611
TEMPERATURE_DELAY_MS = 1200


class Sender:
    def __init__(self):
        self.hot_since = None
        self.latched = False

    def update(self, stamp, values):
        enabled = values['ams_sender'] == 1 and values['ams_thermal'] == 1
        if enabled and values['accu'] > MAX_TEMPERATURE:
            if self.hot_since is None:
                self.hot_since = stamp
            if stamp - self.hot_since >= TEMPERATURE_DELAY_MS:
                self.latched = True
        else:
            self.hot_since = None

    def deadline(self):
        if self.hot_since is not None and not self.latched:
            return self.hot_since + TEMPERATURE_DELAY_MS
        return None

    def status(self, values):
        return dict(kind='ams-ty26-subset-v1' if values['ams_sender'] else 'legacy-test-sender',
                    thermal_enabled=bool(values['ams_sender'] and values['ams_thermal']),
                    overtemperature_latched=self.latched, hot_since_ms=self.hot_since,
                    threshold_raw=MAX_TEMPERATURE, delay_ms=TEMPERATURE_DELAY_MS)
