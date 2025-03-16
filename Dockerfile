# Use a lightweight Python image
FROM python:3.9

# Set working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir flask requests gunicorn mysql-connector-python pyyaml

# Expose port 5000 for Flask
EXPOSE 5000

# Run Flask app with Gunicorn (better for production)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
