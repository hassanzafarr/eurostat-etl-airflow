FROM apache/airflow:2.10.2-python3.11
COPY --chown=airflow:root requirements.txt requirements-dev.txt /opt/airflow/
RUN python -m pip install --no-cache-dir "apache-airflow==2.10.2" \
    -r /opt/airflow/requirements.txt --constraint /home/airflow/constraints.txt \
    && python -m pip install --no-cache-dir "apache-airflow==2.10.2" \
    -r /opt/airflow/requirements-dev.txt
