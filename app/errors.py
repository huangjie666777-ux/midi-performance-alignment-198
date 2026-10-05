"""跨层共享的错误类型。"""


class MidiValidationError(Exception):
    """非法输入材料；``where`` 给出文件/轨道/事件定位。"""

    def __init__(self, message: str, file: str | None = None,
                 track: int | None = None, event: int | None = None):
        super().__init__(message)
        self.message = message
        self.file = file
        self.track = track
        self.event = event

    def detail(self) -> dict:
        d = {"error": self.message}
        if self.file is not None:
            d["file"] = self.file
        if self.track is not None:
            d["track"] = self.track
        if self.event is not None:
            d["event"] = self.event
        return d

