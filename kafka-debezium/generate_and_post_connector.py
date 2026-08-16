import os
import sys

import requests
from dotenv import load_dotenv

# ---------------------------------
# Load environment variables
# ---------------------------------
load_dotenv()


# ---------------------------------
# Validate required variables
# ---------------------------------
def require_env(variable_name: str) -> str:
    value = os.getenv(variable_name)

    if not value:
        raise ValueError(
            f"Required environment variable '{variable_name}' is missing."
        )

    return value


# ---------------------------------
# Kafka Connect configuration
# ---------------------------------
kafka_connect_url = os.getenv(
    "KAFKA_CONNECT_URL",
    "http://127.0.0.1:8083",
).rstrip("/")

connector_name = "postgres-connector"
connector_url = f"{kafka_connect_url}/connectors"


# ---------------------------------
# Debezium PostgreSQL connector
# ---------------------------------
connector_config = {
    "name": connector_name,
    "config": {
        "connector.class": (
            "io.debezium.connector.postgresql.PostgresConnector"
        ),

        # Debezium runs inside Docker.
        "database.hostname": os.getenv(
            "DEBEZIUM_POSTGRES_HOST",
            "postgres",
        ),
        "database.port": os.getenv(
            "DEBEZIUM_POSTGRES_PORT",
            "5432",
        ),

        "database.user": require_env("POSTGRES_USER"),
        "database.password": require_env("POSTGRES_PASSWORD"),
        "database.dbname": require_env("POSTGRES_DB"),

        "topic.prefix": "banking_server",

        "table.include.list": (
            "public.customers,"
            "public.accounts,"
            "public.transactions"
        ),

        "plugin.name": "pgoutput",
        "slot.name": "banking_slot",
        "publication.autocreate.mode": "filtered",
        "tombstones.on.delete": "false",

        # Exact representation is preferable for financial data.
        "decimal.handling.mode": "string",
    },
}


# ---------------------------------
# Submit connector configuration
# ---------------------------------
def create_connector() -> None:
    session = requests.Session()

    # Prevent Windows proxy settings from affecting local requests.
    session.trust_env = False

    try:
        print(f"Checking Kafka Connect at {kafka_connect_url}...")

        health_response = session.get(
            kafka_connect_url,
            timeout=10,
        )
        health_response.raise_for_status()

        print("Kafka Connect is available.")
        print(
            "Debezium will connect to PostgreSQL at "
            f"{connector_config['config']['database.hostname']}:"
            f"{connector_config['config']['database.port']}."
        )

        response = session.post(
            connector_url,
            json=connector_config,
            timeout=30,
        )

        if response.status_code == 201:
            print("Connector created successfully.")

        elif response.status_code == 409:
            print(f"Connector '{connector_name}' already exists.")

        else:
            print(
                f"Failed to create connector "
                f"(HTTP {response.status_code}):"
            )
            print(response.text)
            sys.exit(1)

    except requests.exceptions.ConnectionError as error:
        print(f"Cannot connect to Kafka Connect: {error}")
        sys.exit(1)

    except requests.exceptions.Timeout:
        print("Kafka Connect request timed out.")
        sys.exit(1)

    except requests.exceptions.HTTPError as error:
        print(f"Kafka Connect health check failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        create_connector()

    except ValueError as error:
        print(f"Configuration error: {error}")
        sys.exit(1)