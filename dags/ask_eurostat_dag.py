"""Ask questions about stored Eurostat observations through Airflow's trigger form."""

from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator
from eurostat.questions import DEFAULT_QUESTION, answer_question

with DAG(
    dag_id="ask_eurostat",
    description="Ask Claude Haiku a question about the stored Eurostat data",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    params={
        "question": Param(
            DEFAULT_QUESTION,
            type="string",
            minLength=5,
            maxLength=1500,
            title="Your question",
            description="Ask about GDP or employment for Germany, France, Italy, Spain, Netherlands, Poland or the EU aggregate. Use an observation year, a trend, or a comparison.",
            format="multiline",
        )
    },
    doc_md="""## Ask Eurostat
Click **Trigger DAG**, enter **Your question**, and trigger the run.
When it finishes, select **answer_question > Logs** and search for **ASK EUROSTAT ANSWER**.
Examples: compare Germany and France employment in the latest year; show Germany GDP since 2015;
how did Germany GDP change between 2015 and 2025?
Questions use already-loaded data. Run the ETL DAG first if no observations are stored.
Each run answers one question. Answers and sources are also saved under artifacts/questions.
""",
    tags=["claude", "questions", "eurostat"],
) as dag:
    PythonOperator(
        task_id="answer_question",
        python_callable=answer_question,
        do_xcom_push=False,
        retries=0,
        execution_timeout=timedelta(minutes=4),
    )
