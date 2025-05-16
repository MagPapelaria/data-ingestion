from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from processador import processar_pedidos

default_args = {
    'owner': 'Arthur',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='executa_processamento_pedidos',
    default_args=default_args,
    description='Executa o processamento de pedidos em horários fixos',
    schedule_interval='0 6,12,18,23 * * *',
    start_date=datetime(2025, 5, 16),
    catchup=False,
    tags=['pedidos', 'automatizacao'],
) as dag:

    tarefa = PythonOperator(
        task_id='executar_processador',
        python_callable=processar_pedidos
    )

    tarefa