"""
Example file of interaction with the FastAPI server.

Author
------
Nicolas Rojas
"""

# This script shows how to interact with the API serving the model
# Given the context of this problem, a simple program sending a request makes
# more sense than a graphical user interface, although building one with
# libraries like gradio or streamlit would be trivial given the current script

import requests

ENDPOINT_URL = "http://localhost:8086/predict/"

try:
    data = {
        "id": 0,
        "age": 35.0,
        "annual_income": 107770.0,
        "credit_score": 331.0,
        "loan_amount": 31580.0,
        "loan_duration_years": 28,
        "number_of_open_accounts": 13.0,
        "had_past_default": 0,
    }

    response = requests.post(ENDPOINT_URL, json=data, timeout=30)
    if response.status_code == 200:
        print(response.json())
    else:
        print(f"Failed with status code: {response.status_code}")

except requests.exceptions.RequestException as error:
    print(f"Failed to connect to FastAPI server:\n{error}")
