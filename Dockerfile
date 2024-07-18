FROM python:3.10.6-buster

WORKDIR /app

# Copy frontend
COPY app.py /app/
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY utils/ /app/utils/
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable
ENV FLASK_APP=app.py

# Run app.py when the container launches
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
