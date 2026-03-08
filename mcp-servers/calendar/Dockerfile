FROM python:3.12-slim

WORKDIR /app

COPY mcp-servers/calendar/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-servers/calendar/ .

ENV PYTHONUNBUFFERED=1

EXPOSE 8001
CMD ["python", "server.py"]
