FROM python:3.11-slim

WORKDIR /usr/src/app
COPY . .
RUN pip install --require-hashes -r base-tooling-requirements.txt
RUN pip install --require-hashes -r requirements.txt
EXPOSE 8080
ENV GRADIO_SERVER_PORT="8080"
ENV GRADIO_SERVER_NAME="0.0.0.0"

CMD ["python", "app.py"]