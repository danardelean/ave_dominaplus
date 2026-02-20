class AveThermostatProperties:
    """Store thermostat data."""

    def __init__(self) -> None:
        """Initialize thermostat properties."""
        self.device_id: int = -1
        self.device_name: str = ""
        self.device_response: str = ""
        self.fan_level: int = -1
        self.configuration: str = ""
        self.offset: float = 0.0
        self.season: int = -1
        self.temperature: float = 0.0
        self.mode: str = ""
        self.set_point: float | None = None
        self.forced_mode: int = 0
        self.local_off: str = ""

    @staticmethod
    def from_wts(
        parameters: list[str], records: list[list[str]]
    ) -> AveThermostatProperties:
        """Create thermostat properties from WTS data.

        Args:
            parameters: List of parameter strings.
            records: List of record lists.

        Returns:
            AveThermostatProperties instance populated with WTS data.
        """

        def get_record_value(index):
            if len(records) > 0 and len(records[0]) > index:
                return records[0][index]
            else:
                return None

        props = AveThermostatProperties()
        props.device_id = (
            int(parameters[0])
            if len(parameters) > 0 and str(parameters[0]).isdigit()
            else None
        )
        props.device_name = parameters[0] if len(parameters) > 0 else None
        props.device_response = get_record_value(0)
        props.fan_level = get_record_value(1)
        props.configuration = get_record_value(2)
        props.offset = (
            int(get_record_value(3)) / 10 if get_record_value(3) is not None else None
        )
        props.season = get_record_value(4)
        props.temperature = (
            int(get_record_value(5)) / 10 if get_record_value(5) is not None else None
        )
        props.mode = "1F" if int(get_record_value(8)) == 1 else get_record_value(6)
        props.set_point = (
            int(get_record_value(7)) / 10 if get_record_value(7) is not None else None
        )
        props.forced_mode = get_record_value(8)
        props.local_off = get_record_value(9)
        return props
