import argparse
import os
import random
import sys
import time
from decimal import ROUND_DOWN, Decimal

import psycopg2
from dotenv import load_dotenv
from faker import Faker

# ---------------------------------
# Load environment variables
# ---------------------------------
load_dotenv()


# ---------------------------------
# Project configuration
# ---------------------------------
NUM_CUSTOMERS = 10
ACCOUNTS_PER_CUSTOMER = 2
NUM_TRANSACTIONS = 50

MIN_TXN_AMOUNT = Decimal("1.00")
MAX_TXN_AMOUNT = Decimal("1000.00")

INITIAL_BALANCE_MIN = Decimal("10.00")
INITIAL_BALANCE_MAX = Decimal("1000.00")

CURRENCY = "USD"
SLEEP_SECONDS = 2


# ---------------------------------
# Command-line arguments
# ---------------------------------
parser = argparse.ArgumentParser(
    description="Generate fake banking data and insert it into PostgreSQL."
)

parser.add_argument(
    "--iterations",
    type=int,
    default=None,
    help="Number of iterations to run. Omit this option to run continuously.",
)

args = parser.parse_args()

if args.iterations is not None and args.iterations < 1:
    parser.error("--iterations must be at least 1")


# ---------------------------------
# Faker configuration
# ---------------------------------
fake = Faker()


# ---------------------------------
# Helper functions
# ---------------------------------
def random_money(min_value: Decimal, max_value: Decimal) -> Decimal:
    """Generate a random monetary value with two decimal places."""

    value = Decimal(
        str(
            random.uniform(
                float(min_value),
                float(max_value),
            )
        )
    )

    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_DOWN,
    )


def get_required_environment_variable(variable_name: str) -> str:
    """Return an environment variable or raise an informative error."""

    value = os.getenv(variable_name)

    if not value:
        raise ValueError(
            f"Required environment variable '{variable_name}' is missing."
        )

    return value


def connect_to_postgres():
    """Create and return a PostgreSQL connection."""

    return psycopg2.connect(
        host=get_required_environment_variable("POSTGRES_HOST"),
        port=get_required_environment_variable("POSTGRES_PORT"),
        dbname=get_required_environment_variable("POSTGRES_DB"),
        user=get_required_environment_variable("POSTGRES_USER"),
        password=get_required_environment_variable("POSTGRES_PASSWORD"),
    )


# ---------------------------------
# Data-generation logic
# ---------------------------------
def generate_customers(cursor):
    """Generate customers and return their database IDs."""

    customer_ids = []

    for _ in range(NUM_CUSTOMERS):
        first_name = fake.first_name()
        last_name = fake.last_name()
        email = fake.unique.email()

        cursor.execute(
            """
            INSERT INTO customers (
                first_name,
                last_name,
                email
            )
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (
                first_name,
                last_name,
                email,
            ),
        )

        customer_id = cursor.fetchone()[0]
        customer_ids.append(customer_id)

    return customer_ids


def generate_accounts(cursor, customer_ids):
    """Generate accounts and return their database IDs."""

    account_ids = []

    for customer_id in customer_ids:
        for _ in range(ACCOUNTS_PER_CUSTOMER):
            account_type = random.choice(
                [
                    "SAVINGS",
                    "CHECKING",
                ]
            )

            initial_balance = random_money(
                INITIAL_BALANCE_MIN,
                INITIAL_BALANCE_MAX,
            )

            cursor.execute(
                """
                INSERT INTO accounts (
                    customer_id,
                    account_type,
                    balance,
                    currency
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    customer_id,
                    account_type,
                    initial_balance,
                    CURRENCY,
                ),
            )

            account_id = cursor.fetchone()[0]
            account_ids.append(account_id)

    return account_ids


def generate_transactions(cursor, account_ids):
    """Generate banking transactions."""

    transaction_types = [
        "DEPOSIT",
        "WITHDRAWAL",
        "TRANSFER",
    ]

    for _ in range(NUM_TRANSACTIONS):
        account_id = random.choice(account_ids)
        transaction_type = random.choice(transaction_types)

        amount = random_money(
            MIN_TXN_AMOUNT,
            MAX_TXN_AMOUNT,
        )

        related_account_id = None

        if transaction_type == "TRANSFER" and len(account_ids) > 1:
            eligible_accounts = [
                candidate_id
                for candidate_id in account_ids
                if candidate_id != account_id
            ]

            related_account_id = random.choice(eligible_accounts)

        cursor.execute(
            """
            INSERT INTO transactions (
                account_id,
                txn_type,
                amount,
                related_account_id,
                status
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                account_id,
                transaction_type,
                amount,
                related_account_id,
                "COMPLETED",
            ),
        )


def run_iteration(connection):
    """Generate and save one complete batch of fake banking data."""

    with connection.cursor() as cursor:
        customer_ids = generate_customers(cursor)
        account_ids = generate_accounts(cursor, customer_ids)
        generate_transactions(cursor, account_ids)

    connection.commit()

    print(
        "Generated "
        f"{len(customer_ids)} customers, "
        f"{len(account_ids)} accounts and "
        f"{NUM_TRANSACTIONS} transactions."
    )


# ---------------------------------
# Main program
# ---------------------------------
def main():
    connection = None
    iteration = 0

    try:
        print("Connecting to PostgreSQL...")

        connection = connect_to_postgres()

        print("Connected successfully.")

        while args.iterations is None or iteration < args.iterations:
            iteration += 1

            print(f"\n--- Iteration {iteration} started ---")

            try:
                run_iteration(connection)

            except Exception:
                connection.rollback()
                raise

            print(f"--- Iteration {iteration} finished ---")

            another_iteration_remains = (
                args.iterations is None
                or iteration < args.iterations
            )

            if another_iteration_remains:
                time.sleep(SLEEP_SECONDS)

        print(f"\nCompleted {iteration} iteration(s) successfully.")

    except KeyboardInterrupt:
        print("\nInterrupted by the user. Exiting gracefully...")

    except Exception as error: # noqa: BLE001
        print(f"\nThe data generator failed: {error}")
        sys.exit(1)

    finally:
        if connection is not None:
            connection.close()
            print("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()