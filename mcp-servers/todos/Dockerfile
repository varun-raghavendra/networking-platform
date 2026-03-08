FROM python:3.12-slim

WORKDIR /app

COPY mcp-servers/todos/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-servers/todos/ .

ENV PYTHONUNBUFFERED=1

EXPOSE 8003
CMD ["python", "server.py"]
