#!/usr/bin/env python3
# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""
Script to create DynamoDB test table for local development.
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv


def main():
    """Main function to setup DynamoDB table."""
    # Load .env file
    load_dotenv()

    # Hardcoded local DynamoDB settings
    endpoint_url = 'http://localhost:8001'
    table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'app_data')
    reset_table = os.environ.get('RESET_TABLE', 'false').lower() == 'true'

    print(f"Setting up DynamoDB table '{table_name}' at {endpoint_url}")
    if reset_table:
        print('Reset mode enabled - will delete existing table')

    try:
        ddb = boto3.resource('dynamodb', endpoint_url=endpoint_url)

        # Check if table exists and handle reset
        table_exists = False
        try:
            table = ddb.Table(table_name)
            table.load()
            table_exists = True

            if reset_table:
                print(f"Deleting existing table '{table_name}' for reset...")
                table.delete()
                table.wait_until_not_exists()
                table_exists = False
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise

        # Create table if it doesn't exist
        if not table_exists:
            print(f"Creating table '{table_name}'...")
            ddb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'PK', 'KeyType': 'HASH'},
                    {'AttributeName': 'SK', 'KeyType': 'RANGE'},
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'PK', 'AttributeType': 'S'},
                    {'AttributeName': 'SK', 'AttributeType': 'S'},
                ],
                BillingMode='PAY_PER_REQUEST',
            )
            print(
                f"DynamoDB table '{table_name}' created successfully at {endpoint_url}"
            )
        else:
            print(f"Table '{table_name}' already exists, skipping creation")

    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
