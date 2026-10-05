"""生成真实 SMF 示例到 examples/（.venv/bin/python 运行）。"""

from pathlib import Path

import mido
from mido import Message, MetaMessage, MidiFile, MidiTrack

OUT = Path(__file__).resolve().parent.parent / "examples"
PPQ = 480


def note(track, pitch, start, end, velocity=64):
    """在绝对 tick 位置追加一个音（要求调用顺序非递减）。"""
    track.append(Message("note_on", note=pitch, velocity=velocity,
                         time=start - note.cursor, channel=0))
    track.append(Message("note_off", note=pitch, velocity=0,
                         time=end - start, channel=0))
    note.cursor = end


note.cursor = 0


def reference_midi() -> bytes:
    """Type 1：轨 0 带 tempo（960 tick 处加速），旋律在轨 1。"""
    tempo0 = MidiTrack([
        MetaMessage("set_tempo", tempo=500000, time=0),
        MetaMessage("set_tempo", tempo=250000, time=960),
        MetaMessage("end_of_track", time=0),
    ])
    mel = MidiTrack()
    note.cursor = 0
    # C4 D4 E4 F4，后两音位于加速段。
    note(mel, 60, 0, 480)
    note(mel, 62, 480, 960)
    note(mel, 63, 960, 1440)
    note(mel, 65, 1440, 1920)
    mel.append(MetaMessage("end_of_track", time=0))
    mid = MidiFile(type=1, ticks_per_beat=PPQ)
    mid.tracks = [tempo0, mel]
    return save(mid)


def performance_midi() -> bytes:
    """Type 0 单轨：C4 正确(晚25ms/短50ms)、错音、漏 E4、F4 正确、多奏 G4。"""
    mid = MidiFile(type=0, ticks_per_beat=PPQ)
    track = MidiTrack()
    note.cursor = 0
    note(track, 60, 24, 456)        # +25ms 起音，-50ms 时长
    note(track, 66, 504, 960)       # 应为 62：错音
    # 漏奏 63
    note(track, 72, 960, 1200)      # 多奏
    note(track, 65, 1200, 1680)     # 起音 1250ms，时长 500ms（+250ms）
    note(track, 74, 1680, 1920)     # 额外多奏
    track.append(MetaMessage("end_of_track", time=0))
    mid.tracks = [track]
    return save(mid)


def overlap_midi() -> bytes:
    mid = MidiFile(type=0, ticks_per_beat=PPQ)
    track = MidiTrack([
        Message("note_on", note=60, velocity=64, time=0),
        Message("note_on", note=60, velocity=64, time=10),
        Message("note_off", note=60, velocity=0, time=10),
        Message("note_off", note=60, velocity=0, time=10),
        MetaMessage("end_of_track", time=0),
    ])
    mid.tracks = [track]
    return save(mid)


def orphan_off_midi() -> bytes:
    mid = MidiFile(type=0, ticks_per_beat=PPQ)
    track = MidiTrack([
        Message("note_off", note=60, velocity=0, time=0),
        MetaMessage("end_of_track", time=0),
    ])
    mid.tracks = [track]
    return save(mid)


def type2_midi() -> bytes:
    mid = MidiFile(type=2, ticks_per_beat=PPQ)
    t1 = MidiTrack([
        Message("note_on", note=60, velocity=64, time=0),
        Message("note_off", note=60, velocity=0, time=480),
        MetaMessage("end_of_track", time=0),
    ])
    t2 = MidiTrack([
        Message("note_on", note=62, velocity=64, time=0),
        Message("note_off", note=62, velocity=0, time=480),
        MetaMessage("end_of_track", time=0),
    ])
    mid.tracks = [t1, t2]
    return save(mid)


def smpte_midi() -> bytes:
    mid = MidiFile(type=0)
    mid.ticks_per_beat = -25 * 256 + 40  # 25 fps, 40 subframes
    track = MidiTrack([
        Message("note_on", note=60, velocity=64, time=0),
        Message("note_off", note=60, velocity=0, time=480),
        MetaMessage("end_of_track", time=0),
    ])
    mid.tracks = [track]
    return save(mid)


def dup_tempo_midi() -> bytes:
    mid = MidiFile(type=0, ticks_per_beat=PPQ)
    track = MidiTrack([
        MetaMessage("set_tempo", tempo=500000, time=0),
        MetaMessage("set_tempo", tempo=400000, time=0),
        Message("note_on", note=60, velocity=64, time=0),
        Message("note_off", note=60, velocity=0, time=480),
        MetaMessage("end_of_track", time=0),
    ])
    mid.tracks = [track]
    return save(mid)


def save(mid: MidiFile) -> bytes:
    from io import BytesIO
    buf = BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


FILES = {
    "reference.mid": reference_midi,
    "performance.mid": performance_midi,
    "invalid_overlap.mid": overlap_midi,
    "invalid_orphan_off.mid": orphan_off_midi,
    "invalid_type2.mid": type2_midi,
    "invalid_smpte.mid": smpte_midi,
    "invalid_dup_tempo.mid": dup_tempo_midi,
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, factory in FILES.items():
        path = OUT / name
        path.write_bytes(factory())
        print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
