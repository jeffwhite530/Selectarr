FROM python:latest

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run.py LICENSE config.yml README.md ./
COPY src/ src/

ENTRYPOINT ["python", "run.py"]
