FROM python:3.10-slim

# Install dependencies
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# Run the script
CMD ["python", "readme_render.py"]
