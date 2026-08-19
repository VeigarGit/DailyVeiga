FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --prefix=/install .

COPY tests ./tests

ENV PYTHONPATH=/install/lib/python3.12/site-packages

RUN python -m unittest discover -s tests -v


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=build /install /usr/local

RUN useradd --create-home --uid 10001 dailyveiga \
    && mkdir -p /app/data \
    && chown -R dailyveiga:dailyveiga /app

USER dailyveiga

CMD ["dailyveiga"]
