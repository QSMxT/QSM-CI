# qsm-eval scorer image (pushed to GHCR by .github/workflows/eval-image.yml).
FROM python:3.12-slim

WORKDIR /opt/qsm-eval
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY qsm_eval.py .

ENTRYPOINT ["python", "/opt/qsm-eval/qsm_eval.py"]
