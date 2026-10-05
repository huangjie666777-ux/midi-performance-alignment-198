from io import BytesIO

import pytest

from app.alignment import align
from app.errors import MidiValidationError
from app.melody import extract_melody
from app.parser import parse_smf, validate_target
from app.service import analyze_file, compare
from app.timeline import TickClock, tempo_changes


def _notes(data, track=0, channel=0, label="f"):
    return analyze_file(data, label, track, channel)


def test_example_alignment_cost_and_counts(examples):
    result = compare(examples["reference.mid"], examples["performance.mid"],
                     1, 0, 0, 0)
    assert result["total_cost"] == 5
    assert result["counts"] == {
        "correct": 2, "wrong_pitch": 2, "omitted": 0, "extra": 1}
    first = result["matched"][0]
    assert first["onset_delta_ms"] == 25.0
    assert first["duration_delta_ms"] == -50.0
    assert first["pitch_match"] is True


def test_no_auto_shift_and_tempo_segments(examples):
    notes = analyze_file(examples["reference.mid"], "r", 1, 0)
    starts = [n.start_ms for n in notes]
    # tick 0/480 -> 0/500ms；tick 960 处加速到 250000：960 -> 1000ms。
    assert starts == [0.0, 500.0, 1000.0, 1250.0]
    assert notes[3].end_ms - notes[3].start_ms == 250.0


def test_every_note_appears_once(examples):
    result = compare(examples["reference.mid"], examples["performance.mid"],
                     1, 0, 0, 0)
    ref_used = sorted(m["reference"]["index"] for m in result["matched"])
    perf_used = sorted(m["performance"]["index"] for m in result["matched"])
    assert len(ref_used) == len(set(ref_used))
    assert len(perf_used) == len(set(perf_used))
    all_perf = perf_used + [n["index"] for n in result["errors"]["extra"]]
    assert sorted(all_perf) == [0, 2, 4, 6, 8]


def test_omission_only_when_performance_shorter():
    from tools.generate_examples import reference_midi
    ref_notes = _notes(reference_midi(), track=1)
    # 实奏仅前两个音：后两个应为漏奏。
    import mido
    from mido import Message, MetaMessage, MidiFile, MidiTrack
    mid = MidiFile(type=0, ticks_per_beat=480)
    t = MidiTrack([
        Message("note_on", note=60, velocity=64, time=0),
        Message("note_off", note=60, velocity=0, time=480),
        Message("note_on", note=62, velocity=64, time=0),
        Message("note_off", note=62, velocity=0, time=480),
        MetaMessage("end_of_track", time=0),
    ])
    mid.tracks = [t]
    buf = BytesIO(); mid.save(file=buf)
    perf_notes = _notes(buf.getvalue())
    result = align(ref_notes, perf_notes)
    assert result["counts"]["omitted"] == 2
    assert result["total_cost"] == 2


def test_tie_break_pair_before_omit_extra():
    # 同音高数相等时必须全部配对，即使错音代价 2 == 漏+多 2。
    from app.alignment import align as do_align
    import mido
    from mido import Message, MetaMessage, MidiFile, MidiTrack

    def build(pitches):
        mid = MidiFile(type=0, ticks_per_beat=480)
        msgs = []
        for i, p in enumerate(pitches):
            msgs += [
                Message("note_on", note=p, velocity=64, time=480 if i else 0),
                Message("note_off", note=p, velocity=0, time=480)]
        msgs.append(MetaMessage("end_of_track", time=0))
        mid.tracks = [MidiTrack(msgs)]
        buf = BytesIO(); mid.save(file=buf)
        return _notes(buf.getvalue())

    result = do_align(build([60, 62, 64]), build([60, 63, 64]))
    assert result["counts"] == {
        "correct": 2, "wrong_pitch": 1, "omitted": 0, "extra": 0}


def test_zero_velocity_note_on_closes(examples):
    import mido
    from mido import Message, MetaMessage, MidiFile, MidiTrack
    mid = MidiFile(type=0, ticks_per_beat=480)
    mid.tracks = [MidiTrack([
        Message("note_on", note=60, velocity=80, time=0),
        Message("note_on", note=60, velocity=0, time=240),
        Message("note_on", note=60, velocity=80, time=0),  # 同 tick 先关再开
        Message("note_off", note=60, velocity=0, time=240),
        MetaMessage("end_of_track", time=0),
    ])]
    buf = BytesIO(); mid.save(file=buf)
    notes = _notes(buf.getvalue())
    assert len(notes) == 2


def test_same_tick_close_before_open_zero_duration_rejected():
    import mido
    from mido import Message, MetaMessage, MidiFile, MidiTrack
    mid = MidiFile(type=0, ticks_per_beat=480)
    mid.tracks = [MidiTrack([
        Message("note_on", note=60, velocity=80, time=0),
        Message("note_off", note=60, velocity=0, time=0),  # 零时长
        MetaMessage("end_of_track", time=0),
    ])]
    buf = BytesIO(); mid.save(file=buf)
    with pytest.raises(MidiValidationError) as ei:
        _notes(buf.getvalue())
    assert ei.value.event == 1
    assert "零" in ei.value.message


@pytest.mark.parametrize("name,event", [
    ("invalid_overlap.mid", 1),
    ("invalid_orphan_off.mid", 0),
])
def test_melody_violations_located(examples, name, event):
    with pytest.raises(MidiValidationError) as ei:
        _notes(examples[name])
    assert ei.value.track == 0
    assert ei.value.event == event


@pytest.mark.parametrize("name,needle", [
    ("invalid_type2.mid", "Type 2"),
    ("invalid_smpte.mid", "SMPTE"),
    ("invalid_dup_tempo.mid", "重复 tempo"),
])
def test_structure_violations(examples, name, needle):
    with pytest.raises(MidiValidationError) as ei:
        _notes(examples[name])
    assert needle in ei.value.message


def test_dup_tempo_located_at_track_zero(examples):
    with pytest.raises(MidiValidationError) as ei:
        analyze_file(examples["invalid_dup_tempo.mid"], "f", 0, 0)
    assert ei.value.track == 0


def test_channel_and_track_bounds(examples):
    parsed = parse_smf(examples["reference.mid"], "r")
    with pytest.raises(MidiValidationError):
        validate_target(parsed, 1, 16)
    with pytest.raises(MidiValidationError):
        validate_target(parsed, 9, 0)


def test_type0_must_use_track_zero(examples):
    parsed = parse_smf(examples["performance.mid"], "p")
    with pytest.raises(MidiValidationError) as ei:
        validate_target(parsed, 1, 0)
    assert ei.value.track == 1


def test_other_channel_and_pedal_ignored():
    import mido
    from mido import Message, MetaMessage, MidiFile, MidiTrack
    mid = MidiFile(type=0, ticks_per_beat=480)
    mid.tracks = [MidiTrack([
        Message("control_change", control=64, value=127, time=0),  # 踏板
        Message("note_on", note=70, velocity=64, time=0, channel=3),
        Message("note_off", note=70, velocity=0, time=480, channel=3),
        Message("note_on", note=60, velocity=64, time=0, channel=0),
        Message("note_off", note=60, velocity=0, time=480, channel=0),
        MetaMessage("end_of_track", time=0),
    ])]
    buf = BytesIO(); mid.save(file=buf)
    notes = _notes(buf.getvalue(), channel=0)
    assert [n.pitch for n in notes] == [60]


def test_original_index_preserved(examples):
    notes = analyze_file(examples["reference.mid"], "r", 1, 0)
    # 轨 1 中 note_on 位于事件 0/2/4/6。
    assert [n.index for n in notes] == [0, 2, 4, 6]
    assert [n.pitch for n in notes] == [60, 62, 63, 65]
    assert [n.start_tick for n in notes] == [0, 480, 960, 1440]


def test_file_size_limit():
    with pytest.raises(MidiValidationError) as ei:
        parse_smf(b"\x00" * (2 * 1024 * 1024 + 1), "big")
    assert "超过" in ei.value.message


def test_requests_independent(examples):
    compare(examples["reference.mid"], examples["performance.mid"], 1, 0, 0, 0)
    r2 = compare(examples["reference.mid"], examples["reference.mid"],
                 1, 0, 1, 0)
    assert r2["total_cost"] == 0
