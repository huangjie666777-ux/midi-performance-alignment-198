"""FastAPI 入口：上传参考与实奏 SMF 并返回对齐结果。"""

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .errors import MidiValidationError
from .service import compare

app = FastAPI(title="单旋律 MIDI 演奏对照", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/align")
async def align_endpoint(
    reference: UploadFile = File(..., description="参考 SMF"),
    performance: UploadFile = File(..., description="实奏 SMF"),
    reference_track: int = Form(0, ge=0, description="参考 0 起轨号"),
    reference_channel: int = Form(0, ge=0, le=15),
    performance_track: int = Form(0, ge=0, description="实奏 0 起轨号"),
    performance_channel: int = Form(0, ge=0, le=15),
):
    reference_data = await reference.read()
    performance_data = await performance.read()
    try:
        return compare(
            reference_data, performance_data,
            reference_track, reference_channel,
            performance_track, performance_channel)
    except MidiValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail())

