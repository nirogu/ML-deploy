"""
Backend module for FastAPI application.

Author
------
Nicolas Rojas
"""

# imports
import os
from pydantic import BaseModel
import pandas as pd
from fastapi import FastAPI, HTTPException
import mlflow
import mysql.connector


def check_table_exists(table_name: str):
    """Check whether table exists in raw_data database. If not, create it.

    Parameters
    ----------
    table_name : str
        Name of table to check.
    """
    # count number of rows in predictions data table
    query = f'SELECT COUNT(*) FROM information_schema.tables WHERE table_name="{table_name}"'
    connection = mysql.connector.connect(
        url="http://db_raw:8088",
        user="sqluser",
        password="supersecretaccess2024",
        database="raw_data",
    )
    cursor = connection.cursor()
    cursor.execute(query)
    results = cursor.fetchall()
    # check whether table exists
    if results[0][0] == 0:
        # create table
        print("----- table does not exists, creating it")
        create_sql = f"CREATE TABLE `{table_name}`\
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
        cursor.execute(create_sql)
    else:
        # no need to create table
        print("----- table already exists")

    cursor.close()
    connection.close()


def store_data(dataframe: pd.DataFrame, table_name: str):
    """Store dataframe data in given table, in raw data database.

    Parameters
    ----------
    dataframe : pd.DataFrame
        Dataframe to store in database.
    table_name : str
        Name of the table to store the data.
    """
    check_table_exists(table_name)
    # insert every dataframe row into sql table
    connection = mysql.connector.connect(
        url="http://db_raw:8088",
        user="sqluser",
        password="supersecretaccess2024",
        database="raw_data",
    )
    sql_column_names = ", ".join(
        ["`" + name + "`" for name in dataframe.columns]
    )
    cur = connection.cursor()
    # VALUES in query are %s repeated as many columns are in dataframe
    query = f"INSERT INTO `{table_name}` ({sql_column_names}) \
        VALUES ({', '.join(['%s' for _ in range(dataframe.shape[1])])})"
    dataframe = list(dataframe.itertuples(index=False, name=None))
    cur.executemany(query, dataframe)
    connection.commit()

    cur.close()
    connection.close()


# connect to mlflow
os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://minio:8081"
os.environ["AWS_ACCESS_KEY_ID"] = "access2024minio"
os.environ["AWS_SECRET_ACCESS_KEY"] = "supersecretaccess2024"
mlflow.set_tracking_uri("http://mlflow:8083")
mlflow.set_experiment("mlflow_tracking_model")

# load model
MODEL_NAME = "clients_model"
MODEL_PRODUCTION_URI = f"models:/{MODEL_NAME}/production"
loaded_model = mlflow.pyfunc.load_model(model_uri=MODEL_PRODUCTION_URI)

# create FastAPI app
app = FastAPI()


class ModelInput(BaseModel):
    """Input model for FastAPI endpoint."""

    id: int
    age: float
    annual_income: float
    credit_score: float
    loan_amount: float
    loan_duration_years: int
    number_of_open_accounts: float
    had_past_default: int


@app.post("/predict/")
def predict(item: ModelInput):
    """Predict with loaded model over client data.

    Parameters
    ----------
    item : ModelInput
        Input data for model, received as JSON.

    Returns
    -------
    dict
        Dictionary with prediction.

    Raises
    ------
    HTTPException
        When receiving bad request.
    """
    try:
        global loaded_model
        # get data from model_input
        received_data = item.model_dump()
        # preprocess data
        preprocessed_data = received_data.copy()
        preprocessed_data.pop("id")
        # transform data into DataFrame
        preprocessed_data = pd.DataFrame(
            {
                key: [
                    value,
                ]
                for key, value in preprocessed_data.items()
            }
        )
        # fill nan
        preprocessed_data.fillna(0, inplace=True)
        # predict with model
        prediction = loaded_model.predict(preprocessed_data)
        prediction = int(prediction[0])
        # store data in raw_data database
        received_data = pd.DataFrame(
            {
                key: [
                    value,
                ]
                for key, value in received_data.items()
            }
        )
        received_data["loan_approval"] = prediction
        store_data(received_data, "predictions_data")
        # return prediction as JSON
        return {"prediction": prediction}

    except Exception as error:
        raise HTTPException(
            status_code=400, detail=f"Bad Request\n{error}"
        ) from error
