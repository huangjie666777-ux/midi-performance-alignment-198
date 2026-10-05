# 单旋律 MIDI 演奏对照后端

Python 3.10 / FastAPI / Mido。上传「参考」与「实奏」两份 SMF（标准 MIDI
文件），后端提取指定轨道/通道的单旋律，按速度段精确计算毫秒时间，并用
自实现的动态规划做全局顺序对齐，返回总成本、正确音与错音/漏奏/多奏明细。

## 运行

```bash
# 使用仓库自带虚拟环境
.venv/bin/python tools/generate_examples.py          # 生成 examples/*.mid
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765
```

交互式文档：`http://127.0.0.1:8765/docs`

## 接口

### `GET /health`

返回 `{"status": "ok"}`。

### `POST /align`（`multipart/form-data`）

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `reference` | 文件 | 必填 | 参考 SMF |
| `performance` | 文件 | 必填 | 实奏 SMF |
| `reference_track` | int | 0 | 参考旋律轨号，**0 起** |
| `reference_channel` | int | 0 | 参考通道，0-15 |
| `performance_track` | int | 0 | 实奏旋律轨号，0 起 |
| `performance_channel` | int | 0 | 实奏通道，0-15 |

成功为 `200`，任何材料非法都整次拒绝并返回 `422`，请求之间互相独立、
无共享状态。错误定位形如：

```json
{"detail": {"error": "音高 60 出现孤立的关音事件",
             "file": "performance", "track": 0, "event": 0}}
```

`file` 为 `reference`/`performance`，`track`/`event` 为 0 起轨道号与
轨道内事件序号。

#### 成功响应

- `total_cost`：对齐总成本。同音高配对 0、异音高配对 2、漏奏与多奏各 1。
- `counts`：`correct` / `wrong_pitch` / `omitted` / `extra` 数量。
- `correct`：同音高配对项（含偏差）。
- `errors.wrong_pitch`：异音高配对项（含偏差）。
- `errors.omitted`：参考独有音（漏奏）。
- `errors.extra`：实奏独有音（多奏）。
- `matched`：全部配对项（correct + wrong_pitch），按参考顺序。

每个音保留原 `note_on` 事件序号 `index`、`pitch`、`start_tick`/`end_tick`
与 `start_ms`/`end_ms`。配对项另给：

- `onset_delta_ms`：实奏起音 − 参考起音（毫秒，均以各自文件 tick 0 为起点，
  **不自动平移**）。
- `duration_delta_ms`：实奏时长 − 参考时长（毫秒）。

回溯在同等成本下按 **配对 → 漏奏 → 多奏** 的优先级选择；每个音在结果中
恰好出现一次。

```bash
curl -s -X POST http://127.0.0.1:8765/align \
  -F reference=@examples/reference.mid \
  -F performance=@examples/performance.mid \
  -F reference_track=1 -F reference_channel=0 \
  -F performance_track=0 -F performance_channel=0 | .venv/bin/python -m json.tool
```

## 解析与时间规则

- 仅接受 SMF Type 0 / Type 1 与正 PPQN；Type 2 与 SMPTE（fps 分割）拒绝。
- 每文件 ≤ 2 MiB、≤ 32 轨、≤ 40000 事件；旋律音数 1-1024。
- 逐事件累积 delta tick。正力度 `note_on` 开音；`note_off` 或零力度
  `note_on` 关音。同一 tick **先关再开**。忽略其他通道与踏板等控制器。
- 拒绝：孤立关音、未闭合（缺关音）、零时长（开关同 tick）、同音高重叠。
- tempo：Type 1 从轨 0 读取，Type 0 取唯一轨；缺省为 500000 us/四分音符。
  拒绝零 tempo 及同一 tick 重复 tempo。
- 每个文件独立按速度段，以有理数（`fractions.Fraction`）累加时间后转毫秒，
  避免速度变化处的浮点漂移；输出毫秒保留 3 位小数。

## 模块划分

- `app/parser.py`：字节解析、结构/边界校验。
- `app/timeline.py`：tempo 收集与 tick→毫秒速度段时钟。
- `app/melody.py`：通道音符事件收集、开闭音校验与旋律提取。
- `app/alignment.py`：动态规划全局顺序对齐与回溯。
- `app/service.py`：跨文件流水线（参考/实奏各自解析后对齐）。
- `app/main.py`：HTTP 上传接口与 422 定位。

## 测试

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app tools tests
```

## 示例文件（`tools/generate_examples.py`）

- `reference.mid`：Type 1，轨 0 含两段 tempo（tick 960 加速），旋律在轨 1。
- `performance.mid`：Type 0，含正确音（带起音/时长偏差）、错音、多奏。
- `invalid_overlap.mid` / `invalid_orphan_off.mid`：旋律非法材料。
- `invalid_type2.mid` / `invalid_smpte.mid` / `invalid_dup_tempo.mid`：结构非法。
