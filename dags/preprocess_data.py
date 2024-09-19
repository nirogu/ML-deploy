"""
Airflow DAG to load raw data, process it, split it, and store in database.

Author
------
Nicolas Rojas
"""

# imports
from datetime import datetime
import pandas as pd
from sklearn.model_selection import train_test_split
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.mysql.hooks.mysql import MySqlHook


def check_table_exists(table_name: str):
    """Check whether table exists in clean_data database. If not, create it.

    Parameters
    ----------
    table_name : str
        Name of table to check.
    """
    # count number of rows in data table
    query = f'SELECT COUNT(*) FROM information_schema.tables WHERE table_name="{table_name}"'
    mysql_hook = MySqlHook(mysql_conn_id="clean_data", schema="clean_data")
    connection = mysql_hook.get_conn()
    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    # check whether table exists
    if results[0][0] == 0:
        # create table
        print("----- table does not exists, creating it")
        create_sql = f"CREATE TABLE `{table_name}`\
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


def store_data(dataframe: pd.DataFrame, table_name: str):
    """Store dataframe data in given table, in clean data database.

    Parameters
    ----------
    dataframe : pd.DataFrame
        Dataframe to store in database.
    table_name : str
        Name of the table to store the data.
    """
    check_table_exists(table_name)
    # insert every dataframe row into sql table
    mysql_hook = MySqlHook(mysql_conn_id="clean_data", schema="clean_data")
    sql_column_names = ", ".join(
        ["`" + name + "`" for name in dataframe.columns]
    )
    conn = mysql_hook.get_conn()
    cur = conn.cursor()
    # VALUES in query are %s repeated as many columns are in dataframe
    query = f"INSERT INTO `{table_name}` ({sql_column_names}) \
        VALUES ({', '.join(['%s' for _ in range(dataframe.shape[1])])})"
    dataframe = list(dataframe.itertuples(index=False, name=None))
    cur.executemany(query, dataframe)
    conn.commit()

    return "Data stored"


def preprocess_data():
    """Preprocess raw data and store it in clean_data database."""
    # retrieve raw data
    mysql_hook = MySqlHook(mysql_conn_id="raw_data", schema="raw_data")
    conn = mysql_hook.get_conn()
    query = "SELECT * FROM `raw_clients`"
    dataframe = pd.read_sql(query, con=conn)

    # drop useless column
    dataframe.drop(columns=["id"], inplace=True)
    # fill empty fields
    dataframe.fillna(0, inplace=True)

    # split data: 70% train, 10% val, 20% test
    df_train, df_test = train_test_split(
        dataframe, test_size=0.2, shuffle=True, random_state=1337
    )
    df_train, df_val = train_test_split(
        df_train, test_size=0.125, shuffle=True, random_state=1337
    )

    # store data partitions in database
    store_data(df_train, "clean_clients_train")
    store_data(df_val, "clean_clients_val")
    store_data(df_test, "clean_clients_test")

    return "Data preprocessed"


with DAG(
    "preprocess_data",
    description="Fetch raw data, preprocess it and save it in mysql database",
    start_date=datetime(2024, 9, 18, 0, 2),
    schedule_interval="@once",
) as dag:

    preprocess_task = PythonOperator(
        task_id="preprocess_data", python_callable=preprocess_data
    )
    preprocess_task
