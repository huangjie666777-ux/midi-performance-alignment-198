"""解析、时间线、旋律、对齐的跨文件协作流水线。"""

from .alignment import align
from .melody import extract_melody
from .parser import parse_smf, validate_target
from .timeline import TickClock, tempo_changes


def analyze_file(data: bytes, label: str, track_index: int, channel: int):
    parsed = parse_smf(data, label)
    validate_target(parsed, track_index, channel)
    changes = tempo_changes(parsed, label)
    clock = TickClock(parsed.ppq, changes)
    notes = extract_melody(parsed, track_index, channel, clock)
    return notes


def compare(reference_data: bytes, performance_data: bytes,
            ref_track: int, ref_channel: int,
            perf_track: int, perf_channel: int) -> dict:
    ref_notes = analyze_file(reference_data, "reference",
                             ref_track, ref_channel)
    perf_notes = analyze_file(performance_data, "performance",
                              perf_track, perf_channel)
    result = align(ref_notes, perf_notes)
    result["reference_note_count"] = len(ref_notes)
    result["performance_note_count"] = len(perf_notes)
    return result

