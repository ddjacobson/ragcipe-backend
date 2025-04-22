FROM python:3.9-alpine
WORKDIR ./

RUN apk add --no-cache build-base

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "app.py"]