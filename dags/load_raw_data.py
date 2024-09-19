"""
Airflow DAG to load raw data from speadsheet into database.

Author
------
Nicolas Rojas
"""

# imports
import os
from datetime import datetime
import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.mysql.hooks.mysql import MySqlHook


def check_table_exists():
    """Check whether raw_clients table exists in raw_data database. If not, create it."""
    # count number of rows in raw data table
    query = 'SELECT COUNT(*) FROM information_schema.tables WHERE table_name="raw_clients"'
    mysql_hook = MySqlHook(mysql_conn_id="raw_data", schema="raw_data")
    connection = mysql_hook.get_conn()
    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    # check whether table exists
    if results[0][0] == 0:
        # create table
        print("----- table does not exists, creating it")
        create_sql = "CREATE TABLE `raw_clients`\
            (`id` BIGINT,\
            `age` SMALLINT,\
            `anual_income` BIGINT,\
            `credit_score` SMALLINT,\
            `loan_amount` BIGINT,\
            `loan_duration_years` TINYINT,\
            `number_of_open_accounts` SMALLINT,\
            `had_past_default` TINYINT,\
            `loan_approval` TINYINT\
            )"
        mysql_hook.run(create_sql)
    else:
        # no need to create table
        print("----- table already exists")

    return "Table checked"


def store_data():
    """Store raw data in respective table and database."""
    # Path to the raw training data
    _data_root = "./data"
    _data_filename = "dataset.csv"
    _data_filepath = os.path.join(_data_root, _data_filename)

    # read data and obtain variable names
    dataframe = pd.read_csv(_data_filepath)
    dataframe.rename(columns={"Unnamed: 0": "ID"}, inplace=True)
    sql_column_names = [name.lower() for name in dataframe.columns]

    # insert every dataframe row into sql table
    mysql_hook = MySqlHook(mysql_conn_id="raw_data", schema="raw_data")
    conn = mysql_hook.get_conn()
    cur = conn.cursor()
    # VALUES in query are %s repeated as many columns are in dataframe
    sql_column_names = ", ".join(
        ["`" + name + "`" for name in sql_column_names]
    )
    query = f"INSERT INTO `raw_clients` ({sql_column_names}) \
        VALUES ({', '.join(['%s' for _ in range(dataframe.shape[1])])})"
    dataframe = list(dataframe.itertuples(index=False, name=None))
    cur.executemany(query, dataframe)
    conn.commit()

    return "Data stored"


with DAG(
    "load_data",
    description="Read data from source and store it in raw_data database",
    start_date=datetime(2024, 9, 18, 0, 0),
    schedule_interval="@once",
) as dag:

    check_table_task = PythonOperator(
        task_id="check_table_exists", python_callable=check_table_exists
    )
    store_data_task = PythonOperator(
        task_id="store_data", python_callable=store_data
    )

    check_table_task >> store_data_task
