"""全局顺序对齐（自行动态规划）。

代价：同音高配对 0、异音高配对 2、漏奏（参考独有）1、多奏（实奏独有）1。
回溯在同成本下按 配对 -> 漏奏 -> 多奏 的优先级选择；每音恰出现一次。
"""

from .melody import Note


def _ms(value) -> float:
    return round(float(value), 3)


def align(reference: list[Note], performance: list[Note]) -> dict:
    n_ref = len(reference)
    n_perf = len(performance)

    # dp[i][j]：参考前 i 音、实奏前 j 音的最小总成本。
    dp = [[0] * (n_perf + 1) for _ in range(n_ref + 1)]
    for i in range(1, n_ref + 1):
        dp[i][0] = i
    for j in range(1, n_perf + 1):
        dp[0][j] = j
    for i in range(1, n_ref + 1):
        for j in range(1, n_perf + 1):
            pair_cost = 0 if reference[i - 1].pitch == performance[j - 1].pitch else 2
            dp[i][j] = min(
                dp[i - 1][j - 1] + pair_cost,   # 配对（最高优先）
                dp[i - 1][j] + 1,               # 漏奏
                dp[i][j - 1] + 1,               # 多奏
            )

    matched = []
    correct = []
    wrong = []
    omitted = []
    extra = []

    i, j = n_ref, n_perf
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            pair_cost = 0 if reference[i - 1].pitch == performance[j - 1].pitch else 2
            # 同成本优先：配对 -> 漏奏 -> 多奏。
            if dp[i][j] == dp[i - 1][j - 1] + pair_cost:
                ref_note = reference[i - 1]
                perf_note = performance[j - 1]
                onset_delta = _ms(perf_note.start_ms - ref_note.start_ms)
                duration_delta = _ms(
                    (perf_note.end_ms - perf_note.start_ms)
                    - (ref_note.end_ms - ref_note.start_ms))
                item = {
                    "reference": ref_note.to_dict(),
                    "performance": perf_note.to_dict(),
                    "onset_delta_ms": onset_delta,
                    "duration_delta_ms": duration_delta,
                    "pitch_match": pair_cost == 0,
                }
                matched.append(item)
                (correct if pair_cost == 0 else wrong).append(item)
                i -= 1
                j -= 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            omitted.append(reference[i - 1].to_dict())
            i -= 1
            continue
        extra.append(performance[j - 1].to_dict())
        j -= 1

    matched.reverse()
    correct.reverse()
    wrong.reverse()
    omitted.reverse()
    extra.reverse()

    return {
        "total_cost": dp[n_ref][n_perf],
        "counts": {
            "correct": len(correct),
            "wrong_pitch": len(wrong),
            "omitted": len(omitted),
            "extra": len(extra),
        },
        "correct": correct,
        "errors": {
            "wrong_pitch": wrong,
            "omitted": omitted,
            "extra": extra,
        },
        "matched": matched,
    }

