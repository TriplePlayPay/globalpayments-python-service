FROM python:3.11.9-alpine@sha256:0b5ed25d3cc27cd35c7b0352bac8ef2ebc8dd3da72a0c03caaf4eb15d9ec827a
WORKDIR /app

RUN mkdir -p ~/.ssh
RUN chmod 700 ~/.ssh

RUN pip install poetry
RUN poetry config virtualenvs.create false --local

COPY poetry.lock .
COPY pyproject.toml .
#RUN poetry install
RUN \
    apk add --update --no-cache \
      --virtual .tmp-build-deps \
      gcc libc-dev linux-headers postgresql-dev libffi-dev && \
    pip install poetry && \
    poetry config virtualenvs.create false --local && \
    poetry install && \
    apk del .tmp-build-deps
COPY app.py .
COPY . .
#USER 405
CMD ["python", "app.py"]
