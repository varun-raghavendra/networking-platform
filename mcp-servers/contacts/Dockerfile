FROM python:3.12-slim

WORKDIR /app

COPY mcp-servers/contacts/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-servers/contacts/ .

ENV PYTHONUNBUFFERED=1

EXPOSE 8002
CMD ["python", "server.py"]
