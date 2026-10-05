"""从指定轨道/通道提取单旋律音序列。

同 tick 先关音再开音；拒绝孤立关音、未闭合、零时长与重叠音。
忽略其他通道与踏板等非音符事件。
"""

from dataclasses import dataclass
from fractions import Fraction

from .errors import MidiValidationError
from .timeline import TickClock

MIN_NOTES = 1
MAX_NOTES = 1024


@dataclass(frozen=True)
class Note:
    index: int          # 原事件序号（note_on 的轨道内 0 起索引）
    pitch: int
    start_tick: int
    end_tick: int
    start_ms: Fraction
    end_ms: Fraction

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "pitch": self.pitch,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "start_ms": float(self.start_ms),
            "end_ms": float(self.end_ms),
        }


def extract_melody(parsed, track_index: int, channel: int,
                   clock: TickClock) -> list[Note]:
    def fail(idx: int | None, text: str) -> MidiValidationError:
        return MidiValidationError(text, file=parsed.file,
                                   track=track_index, event=idx)

    track = parsed.tracks[track_index]

    # 收集本通道音符事件 (index, tick, kind[1=关 0=开], pitch)。
    events = []
    tick = 0
    for idx, msg in enumerate(track):
        tick += msg.time
        if msg.is_meta or getattr(msg, "channel", None) != channel:
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            events.append((idx, tick, 0, msg.note))
        elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0):
            events.append((idx, tick, 1, msg.note))

    # 同 tick 先关再开：关音先闭合已存在的音；若该音在同 tick 才开，
    # 则挂起到开音处闭合并判零时长。仍挂起者为孤立关音。
    events.sort(key=lambda e: e[1])

    notes: list[Note] = []
    open_by_pitch: dict[int, tuple[int, int]] = {}
    pending_close: dict[int, int] = {}   # pitch -> 关音事件 index
    cur_tick = None

    def close_note(pitch, on_idx, on_tick, off_idx, off_tick):
        if off_tick == on_tick:
            raise fail(off_idx, f"音高 {pitch} 音时长为零（开关同 tick）")
        notes.append(Note(
            index=on_idx, pitch=pitch, start_tick=on_tick,
            end_tick=off_tick, start_ms=clock.ms_at(on_tick),
            end_ms=clock.ms_at(off_tick)))

    for idx, ev_tick, kind, pitch in events:
        if ev_tick != cur_tick:
            for pending_pitch, off_idx in pending_close.items():
                raise fail(off_idx, f"音高 {pending_pitch} 出现孤立的关音事件")
            pending_close.clear()
            cur_tick = ev_tick

        if kind == 1:
            if pitch in open_by_pitch:
                on_idx, on_tick = open_by_pitch.pop(pitch)
                close_note(pitch, on_idx, on_tick, idx, ev_tick)
            else:
                pending_close[pitch] = idx
        else:
            if pitch in pending_close:
                off_idx = pending_close.pop(pitch)
                close_note(pitch, idx, ev_tick, off_idx, ev_tick)
            if pitch in open_by_pitch:
                raise fail(idx, f"音高 {pitch} 重叠：上一音尚未关音")
            open_by_pitch[pitch] = (idx, ev_tick)

    for pending_pitch, off_idx in pending_close.items():
        raise fail(off_idx, f"音高 {pending_pitch} 出现孤立的关音事件")
    if open_by_pitch:
        pitch, (on_idx, _) = next(iter(open_by_pitch.items()))
        raise fail(on_idx, f"音高 {pitch} 的音未闭合（缺少关音事件）")

    notes.sort(key=lambda n: (n.start_tick, n.index))
    if len(notes) < MIN_NOTES:
        raise MidiValidationError("旋律至少包含 1 个音", file=parsed.file,
                                 track=track_index)
    if len(notes) > MAX_NOTES:
        raise MidiValidationError(
            f"旋律音数 {len(notes)} 超过上限 {MAX_NOTES}",
            file=parsed.file, track=track_index)
    return notes
