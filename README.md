# ML-deploy

**By: Nicolas Rojas**

MLOps deployment pipeline.

This repository contains the source code to train and deploy a binary classification predictive model, using Airflow, Minio and Mlflow. By default, this repository solves the classification problem defined by the [loan aproval dataset](data/dataset.csv).

## Installation and execution

Run the following commands to install and run this project:

```shell
git clone https://github.com/nirogu/ML-deploy --depth 1
cd ML-deploy
docker compose -f docker-compose.yaml --env-file config.env up airflow-init --build
docker compose -f docker-compose.yaml --env-file config.env up --build -d
```

To stop the service, run the folowing command:

```shell
docker compose down --volumes --remove-orphans
```

## Usage

- The Apache Airflow dashboard will be found on [localhost:8080](http://localhost:8080). From there, you can manage the DAGs as described in the [project documentation](https://airflow.apache.org/docs/apache-airflow/stable/index.html).
- The MLflow dashboard will be found on [localhost:8083](http://localhost:8083). From there, you can manage the experiments and models as described in the [project documentation](https://mlflow.org/docs/latest/index.html).
- The MinIO dashboard will be found on [localhost:8082](http://localhost:8082). From there, you can manage the storage buckets used by MLflow as described in the [project documentation](https://min.io/docs/minio/linux/index.html), although usually this is not needed.
- A JupyterLab service can be accessed at [localhost:8085](http://localhost:8085). From there, you can run experiments on the mounted python environment, using Jupyter notebooks as you would in the local environment, as presented in the [example](notebooks/classification_experiments.ipynb).
- The inference API can be accessed through [localhost:8086](http://localhost:8086), and the documentation can be found in the [docs endpoint](http://localhost:8086/docs).

## Rationale

It is assumed that the data is already collected and presented as a file. If that were not the case, it would be simple to edit the [data consuming DAG](dags/load_raw_data.py) to obtain the data as needed. Besides, it is assumed that data science related tasks have already been performed over the dataset, so that a machine learning model has already been defined, trained and tested in a local environment. Thus, the main challenge consists on getting the model to production, in a way that updates in the data, the model architecture, or in the training process can be automatically handled; and the model is permanently available for usage upon request. This is why a complete MLOps pipeline will be designed and explained.

This project's architecture is presented in the following diagram:

![Architecture diagram](architecture.svg)

The architecture works as follows:
- First, an [Airflow](https://airflow.apache.org/) service is mounted to coordinate and monitor three different workflows: data loading, data preprocessing, and model training. These workflows are represented as Airflow DAGs.
- The data loading workflow can be found in [load_raw_data](dags/load_raw_data.py). Its function is retrieving the data from source and storing it (unprocessed) in a SQL database created for this purpose, called _raw-data_.
- The data preprocessing workflow can be found in [preprocess_data](dags/preprocess_data.py). Its function is retrieving the raw data from the _raw-data_ data base, cleaning it, transforming it, splitting it in train/validation/test partitions, and storing the result in a SQL database created for this purpose, called _clean-data_.
- The model training workflow can be found in [train_model](dags/train_model.py). Its function is retrieving the clean data from the _clean-data_ data base, defining a machine learning model (in this particular case, a [scikit-learn](https://scikit-learn.org/stable/index.html) model), training the model, testing it, and storing the artifacts and training metadata with a mlflow experiment.
- A [MLflow](https://mlflow.org/) service is mounted to coordinate the experimentation process, controlling the model versioning and deploying the necessary pretrained models. This is done by storing the model artifacts in a [MinIO](https://min.io/) bucket and the experimentation metadata in a SQL database created for this purpose. MLflow will also serve a model tagged as production ready to be used by the application API.
- A RestAPI is mounted with [FastAPI](https://fastapi.tiangolo.com), in the [backend script](src/back/main.py). This program loads the _production_ tagged model from MLflow and uses it to make predictions on the structured data received as a POST request. Besides returning the prediction, it also stores both the input and the prediction in a separate table in the _raw-data_ database. An example on how to consume the API is presented in the [frontend script](src/front/main.py).
- Every service is defined by its respective [docker image](./docker/) and everything is mounted with [Docker compose](./docker-compose.yaml).

Thus, a typical workflow would consist in running the Airflow DAGs to obtain the data, training the model with its respective DAG, reviewing its performance and serving it with MLflow, and consuming it by making POST requests to the API.

- *Extra 1:* An additional (and optional) JupyterLab service is mounted to help the data scientists run experiments as they would in a local environment. An example is presented in the [included notebook](notebooks/classification_experiments.ipynb).
- *Extra 2:* An alternative way of deploying the services is pushing each independent container to a docker container registry (e.g. AWS ECR, DockerHub, etc.) and pulling them when building the complete project. This can be done with [GitHub Actions](https://docs.github.com/actions) that build and push new versions of the docker images when there are changes in the code repository. An example of such a workflow is presented in [the GitHub Actions folder](.github/workflows/airflow-publish-container.yaml) (remember to store any sensitive information as [GitHub secrets](https://docs.github.com/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions) instead of writing it in the code).
