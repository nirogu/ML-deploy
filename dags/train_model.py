"""
Airflow DAG to load clean data and train model with MLflow.

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
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score
import mlflow
from mlflow.models import infer_signature


def get_data(table_name: str, target_variable: str):
    """Get data from clean_data database.

    Parameters
    ----------
    table_name : str
        Name of table to get data from.
    target_variable : str
        Name of the target variable in the classification problem.
    """
    # connect to clean database
    mysql_hook = MySqlHook(mysql_conn_id="clean_data", schema="clean_data")
    sql_connection = mysql_hook.get_conn()
    # get all available data
    query = f"SELECT * FROM `{table_name}`"
    dataframe = pd.read_sql(query, con=sql_connection)
    # return input features and target variable
    return dataframe.drop(columns=[target_variable]), dataframe[target_variable]


def train_model():
    """Train model with clean data and save artifacts with MLflow."""
    # get data partitions
    target_variable = "loan_approval"
    X_train, y_train = get_data("clean_clients_train", target_variable)
    X_val, y_val = get_data("clean_clients_val", target_variable)
    X_test, y_test = get_data("clean_clients_test", target_variable)

    # define preprocessor and classifier
    categorical_feature = "had_past_default"
    numerical_features = [
        category
        for category in X_train.columns
        if category != categorical_feature
    ]
    preprocessor = ColumnTransformer(
        transformers=[
            ("numerical", StandardScaler(), numerical_features),
            ("categorical", "passthrough", [categorical_feature]),
        ]
    )
    hyperparameters = {
        "classifier__n_estimators": 168,
        "classifier__max_depth": 6,
        "classifier__learning_rate": 0.001,
    }
    classifier = GradientBoostingClassifier(**hyperparameters)
    pipeline = Pipeline(
        steps=[("preprocessor", preprocessor), ("classifier", classifier)]
    )

    # connect to mlflow
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://minio:8081"
    os.environ["AWS_ACCESS_KEY_ID"] = "access2024minio"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "supersecretaccess2024"
    mlflow.set_tracking_uri("http://mlflow:8083")
    mlflow.set_experiment("mlflow_tracking_model")
    mlflow.sklearn.autolog(
        log_model_signatures=True,
        log_input_examples=True,
        registered_model_name="clients_model",
    )

    # open mlflow run
    with mlflow.start_run(run_name="autolog_pipe_model") as run:
        # train model
        pipeline.fit(X_train, y_train)
        y_pred_val = pipeline.predict(X_val)
        y_pred_test = pipeline.predict(X_test)
        # log metrics
        mlflow.log_metric("f1_score_val", f1_score(y_val, y_pred_val))
        mlflow.log_metric("f1_score_test", f1_score(y_test, y_pred_test))
        # log model
        signature = infer_signature(X_test, y_pred_test)
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="clients_model",
            signature=signature,
            registered_model_name="clients_model",
        )


with DAG(
    "train_model",
    description="Fetch clean data from database, train model, save artifacts with MLflow and register model",
    start_date=datetime(2024, 9, 18, 0, 5),
    schedule_interval="@once",
) as dag:

    train_model_task = PythonOperator(
        task_id="train_model", python_callable=train_model
    )
    train_model_task
