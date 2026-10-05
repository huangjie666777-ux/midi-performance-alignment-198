"""速度段时间线：累积 tick -> 精确有理毫秒。

Type 1 从轨 0 取 tempo；Type 0 取唯一轨。默认 500000 us/四分音符。
拒绝零 tempo 与同 tick 重复 tempo。
"""

from fractions import Fraction

from .errors import MidiValidationError

DEFAULT_TEMPO_US = 500000


def tempo_changes(parsed, file_label: str) -> list[tuple[int, int]]:
    """返回按 tick 排序的 (tick, us_per_beat)，不含默认值。"""
    tempo_track = parsed.tracks[0]
    tick = 0
    changes: list[tuple[int, int, int]] = []
    for idx, msg in enumerate(tempo_track):
        tick += msg.time
        if msg.type == "set_tempo":
            if msg.tempo <= 0:
                raise MidiValidationError(
                    f"tempo 必须为正（得到 {msg.tempo}）",
                    file=file_label, track=0, event=idx)
            changes.append((tick, msg.tempo, idx))

    seen: set[int] = set()
    for tick_at, _, idx in changes:
        if tick_at in seen:
            raise MidiValidationError(
                f"tick {tick_at} 处存在重复 tempo",
                file=file_label, track=0, event=idx)
        seen.add(tick_at)
    changes.sort(key=lambda item: item[0])
    return [(tick_at, tempo) for tick_at, tempo, _ in changes]


class TickClock:
    """按速度段累加的精确时钟，单位为 Fraction 毫秒。"""

    def __init__(self, ppq: int, changes: list[tuple[int, int]]):
        self._ppq = ppq
        self._segments: list[tuple[int, Fraction, Fraction]] = []
        cur_tick = 0
        cur_ms = Fraction(0)
        cur_tempo = DEFAULT_TEMPO_US
        for change_tick, tempo in changes:
            cur_ms += (Fraction(change_tick - cur_tick) * cur_tempo
                       / ppq / 1000)
            cur_tick = change_tick
            cur_tempo = tempo
            self._segments.append((cur_tick, cur_ms, Fraction(cur_tempo)))

    def ms_at(self, tick: int) -> Fraction:
        base_tick = 0
        base_ms = Fraction(0)
        tempo = Fraction(DEFAULT_TEMPO_US)
        for seg_tick, seg_ms, seg_tempo in self._segments:
            if seg_tick > tick:
                break
            base_tick, base_ms, tempo = seg_tick, seg_ms, seg_tempo
        return base_ms + Fraction(tick - base_tick) * tempo / self._ppq / 1000
