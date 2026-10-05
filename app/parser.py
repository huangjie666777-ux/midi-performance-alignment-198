"""SMF 上传字节解析与结构校验。

约束：Type 0/1、正 PPQN（拒绝 Type 2 与 SMPTE）；每文件 <= 2 MiB、
<= 32 轨、<= 40000 事件；轨号为 0 起，通道 0-15。
"""

from dataclasses import dataclass
from io import BytesIO

import mido

from .errors import MidiValidationError

MAX_BYTES = 2 * 1024 * 1024
MAX_TRACKS = 32
MAX_EVENTS = 40000


@dataclass(frozen=True)
class ParsedMidi:
    file: str
    midi_type: int
    ppq: int
    tracks: list


def parse_smf(data: bytes, file: str) -> ParsedMidi:
    if len(data) == 0:
        raise MidiValidationError("文件为空", file=file)
    if len(data) > MAX_BYTES:
        raise MidiValidationError(
            f"文件超过 {MAX_BYTES} 字节（实际 {len(data)}）", file=file)
    try:
        mid = mido.MidiFile(file=BytesIO(data))
    except Exception as exc:  # mido 的解析异常类型不统一
        raise MidiValidationError(f"无法解析为标准 SMF：{exc}", file=file)

    if mid.type not in (0, 1):
        raise MidiValidationError(
            "不支持 Type 2 MIDI 文件" if mid.type == 2
            else f"未知 MIDI 文件类型 {mid.type}", file=file)

    ticks_per_beat = mid.ticks_per_beat
    if ticks_per_beat is None or ticks_per_beat < 0:
        raise MidiValidationError(
            "SMPTE 时间分割（fps 格式）不受支持，仅支持正 PPQN", file=file)
    if ticks_per_beat == 0:
        raise MidiValidationError("PPQN 必须为正整数", file=file)

    tracks = list(mid.tracks)
    if not tracks:
        raise MidiValidationError("MIDI 文件不含任何轨道", file=file)
    if len(tracks) > MAX_TRACKS:
        raise MidiValidationError(
            f"轨道数 {len(tracks)} 超过上限 {MAX_TRACKS}", file=file)
    total_events = sum(len(t) for t in tracks)
    if total_events > MAX_EVENTS:
        raise MidiValidationError(
            f"事件数 {total_events} 超过上限 {MAX_EVENTS}", file=file)

    return ParsedMidi(file=file, midi_type=mid.type, ppq=ticks_per_beat,
                      tracks=tracks)


def validate_target(parsed: ParsedMidi, track_index: int,
                    channel: int) -> None:
    if not isinstance(track_index, int):
        raise MidiValidationError("轨号必须为整数", file=parsed.file)
    if not 0 <= channel <= 15:
        raise MidiValidationError(
            f"通道号 {channel} 超出 0-15", file=parsed.file)
    if parsed.midi_type == 0 and track_index != 0:
        raise MidiValidationError(
            "Type 0 仅有唯一轨道，轨号必须为 0",
            file=parsed.file, track=track_index)
    if not 0 <= track_index < len(parsed.tracks):
        raise MidiValidationError(
            f"轨号 {track_index} 超出范围（共 {len(parsed.tracks)} 轨）",
            file=parsed.file)
