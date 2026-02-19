from homeassistant.backup_restore import _LOGGER


class AveMapCommand:
    def __init__(self):
        self.command_id: int = -1
        self.command_name: str = ""
        self.command_type: int = -1
        self.command_X: int = -1
        self.command_Y: int = -1
        self.icod: str = ""
        self.ico1: str = ""
        self.ico2: str = ""
        self.ico3: str = ""
        self.ico4: str = ""
        self.ico5: str = ""
        self.ico6: str = ""
        self.ico7: str = ""
        self.icoc: str = ""
        self.device_id: int = -1
        self.device_family: int = -1

    @staticmethod
    def _readRecordValue(record: list[str], index: int) -> str:
        if index < len(record):
            return record[index]
        return ""

    @classmethod
    def FromWsRecord(cls, record: list[str]):
        instance = cls()
        try:
            instance.command_id = int(cls._readRecordValue(record, 0))
            instance.command_name = cls._readRecordValue(record, 1)
            instance.command_type = int(cls._readRecordValue(record, 2))
            instance.command_X = int(cls._readRecordValue(record, 3))
            instance.command_Y = int(cls._readRecordValue(record, 4))
            instance.icod = cls._readRecordValue(record, 5)
            instance.ico1 = cls._readRecordValue(record, 6)
            instance.ico2 = cls._readRecordValue(record, 7)
            instance.ico3 = cls._readRecordValue(record, 8)
            instance.ico4 = cls._readRecordValue(record, 9)
            instance.ico5 = cls._readRecordValue(record, 10)
            instance.ico6 = cls._readRecordValue(record, 11)
            instance.ico7 = cls._readRecordValue(record, 12)
            instance.icoc = cls._readRecordValue(record, 13)
            instance.device_id = (
                int(cls._readRecordValue(record, 14))
                if cls._readRecordValue(record, 14).isdigit()
                else -1
            )
            instance.device_family = int(cls._readRecordValue(record, 15))
        except (ValueError, IndexError) as e:
            _LOGGER.error("Error parsing command record: %s", str(e))
        return instance


class AveArea:
    def __init__(self, id: int, name: str, order: int):
        self.id: int = id
        self.name: str = name
        self.order: int = order
        self.commands: list[AveMapCommand] = []
        self.commands_loaded: bool = False


class AveMap:
    def __init__(self):
        self.areas_loaded: bool = False
        self.command_loaded: bool = False
        self.areas: dict[int, AveArea] = {}

    def LoadAreasFromWsRecords(self, records: list[list]):
        for record in records:
            area_id = int(record[0])
            area_name = record[1]
            area_order = int(record[2])
            self.areas[area_id] = AveArea(area_id, area_name, area_order)
        self.areas_loaded = True

    def LoadAreaCommands(self, area_id: int, records: list[list[str]]):
        area = self.areas.get(area_id)
        if area:
            for record in records:
                command = AveMapCommand.FromWsRecord(record)
                area.commands.append(command)
            area.commands_loaded = True

            if all(a.commands_loaded for a in self.areas.values()):
                self.command_loaded = True

    def GetCommandsByFamily(self, family: int) -> list[AveMapCommand]:
        commands: list[AveMapCommand] = []
        for area in self.areas.values():
            for command in area.commands:
                if command.device_family == family:
                    commands.append(command)
        return commands

    def GetCommandByIdAndFamily(
        self, command_id: int, family: int
    ) -> AveMapCommand | None:
        for area in self.areas.values():
            for command in area.commands:
                if command.command_id == command_id and command.device_family == family:
                    return command
        return None

    def GetCommandByDeviceId(self, device_id: int) -> AveMapCommand | None:
        for area in self.areas.values():
            for command in area.commands:
                if command.device_id == device_id:
                    return command
        return None

    def GetCommandByDeviceIdAndFamily(
        self, device_id: int, family: int
    ) -> AveMapCommand | None:
        for area in self.areas.values():
            for command in area.commands:
                if command.device_id == device_id and command.device_family == family:
                    return command
        return None

    def get_map(self, map_name):
        return self.areas.get(map_name)
