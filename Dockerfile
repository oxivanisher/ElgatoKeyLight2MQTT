FROM python:3-slim
RUN mkdir -p /app
WORKDIR /app/
COPY requirements.txt .
RUN pip install --trusted-host pypi.python.org  --trusted-host pypi.org  --trusted-host files.pythonhosted.org --no-cache-dir -r requirements.txt
COPY src/main.py .

# Install python dependencies:
CMD ["python3", "main.py"]
