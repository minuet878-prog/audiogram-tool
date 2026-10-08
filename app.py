import re

from flask import Flask, render_template, request

from audiogram import chart
from audiogram.classify import degree, hearing_type, pta

app = Flask(__name__)

EARS = {"right": "右耳", "left": "左耳"}
CONDUCTIONS = {
    "ac": ("氣導", chart.FREQUENCIES),
    "bc": ("骨導", (500, 1000, 2000, 4000)),
}


def parse(form):
    """Return ({ear: {conduction: {freq: dB}}}, {field name: error message})."""
    data, errors = {}, {}
    for ear, ear_name in EARS.items():
        data[ear] = {}
        for conduction, (conduction_name, frequencies) in CONDUCTIONS.items():
            values = data[ear][conduction] = {}
            for freq in frequencies:
                name = f"{ear}_{conduction}_{freq}"
                raw = form.get(name, "").strip()
                if not raw:
                    continue
                # int() alone also accepts "1_0" and full-width digits
                value = int(raw) if re.fullmatch(r"-?[0-9]{1,3}", raw) else None
                if value is None or value % 5 or not chart.DB_MIN <= value <= chart.DB_MAX:
                    errors[name] = (
                        f"{ear_name}{conduction_name} {freq} Hz：請輸入 "
                        f"{chart.DB_MIN} 到 {chart.DB_MAX} 之間、5 的倍數"
                    )
                else:
                    values[freq] = value
    return data, errors


def summarize(ear_data):
    """Result of one ear, or None if nothing was entered for it."""
    if not ear_data["ac"] and not ear_data["bc"]:
        return None
    ac_pta = pta(ear_data["ac"])
    if ac_pta is None:
        return {"message": "氣導資料不足，無法計算"}
    return {
        "pta": f"{ac_pta:g}",
        "degree": degree(ac_pta),
        "type": hearing_type(ac_pta, pta(ear_data["bc"])) or "缺骨導資料，無法判斷",
    }


@app.route("/", methods=["GET", "POST"])
def index():
    data, errors = parse(request.form)
    results, marks = {}, {}
    if not errors:
        for ear in EARS:
            summary = summarize(data[ear])
            if summary:
                results[ear] = summary
                marks[ear] = {c: chart.points(v) for c, v in data[ear].items()}
    return render_template(
        "index.html",
        ears=EARS,
        conductions=CONDUCTIONS,
        form=request.form,
        errors=errors,
        results=results,
        marks=marks,
        chart=chart,
    )


if __name__ == "__main__":
    app.run()
