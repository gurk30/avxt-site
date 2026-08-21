FROM python:3.12-alpine
WORKDIR /app
COPY server.py ./
COPY docs/ ./docs/
ENV DATA_DIR=/data
EXPOSE 8080
CMD ["python", "server.py"]
