FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app
COPY unit/feature-0004-browser-automation/src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY unit/feature-0004-browser-automation/src/app.py .
COPY unit/feature-0004-browser-automation/src/ctl.py .

ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
