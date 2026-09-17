FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
# The speech engines are an optional extra: the ASR one pulls in a large native
# runtime, so it stays out of the default image and the app falls back to the
# browser's own engines. Build with `--build-arg EXTRAS=speech` to include it.
ARG EXTRAS=""
RUN pip install --no-cache-dir ".${EXTRAS:+[$EXTRAS]}"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

