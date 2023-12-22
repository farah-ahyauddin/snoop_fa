import pandas as pd

from data_loader import load_data_from_zips
from data_processing import (
    json_to_dataframe,
    remove_invalid_currencies,
    remove_invalid_dates,
    remove_duplicates,
    combine_and_remove_duplicates
)
from database_operations import insert_data_to_postgres


def main():
    folder_path = 'data'  # Specify the folder containing the zipped files
    all_data = load_data_from_zips(folder_path)

    for data in all_data:
        all_transactions_df = json_to_dataframe(data)

        valid_currencies_df, invalid_currencies_df = remove_invalid_currencies(all_transactions_df)

        valid_dates_df, invalid_dates_df = remove_invalid_dates(valid_currencies_df)
        valid_duplicates_df, invalid_duplicates_df = remove_duplicates(valid_dates_df)

        combined_valid_df, combined_invalid_df = combine_and_remove_duplicates(
            [valid_currencies_df, valid_dates_df, valid_duplicates_df],
            [invalid_currencies_df, invalid_dates_df, invalid_duplicates_df]
        )

        invalid_records = combined_invalid_df.drop_duplicates().drop(columns=['customerName'])

        transactions = all_transactions_df[
            ~all_transactions_df['transactionId'].isin(invalid_records['transactionId'])]
        transactions = transactions.drop_duplicates().drop(columns=['customerName'])

        customers = transactions[['customerId', 'transactionDate']].drop_duplicates()
        # Sort the DataFrame based on the transactionDate column in descending order
        customers = customers.sort_values(by='transactionDate', ascending=False)

        invalid_records['data_quality_check'] = None  # new column for type of dq check

        invalid_records.loc[
            invalid_records.index.isin(invalid_currencies_df.index), 'data_quality_check'] = 'currency'
        invalid_records.loc[invalid_records.index.isin(invalid_dates_df.index), 'data_quality_check'] = 'transaction_date'
        invalid_records.loc[
            invalid_records.index.isin(invalid_duplicates_df.index), 'data_quality_check'] = 'duplicate'

        error_logs = invalid_records[~(invalid_records['transactionDate'].notna() | invalid_records['transactionDate'].astype(str).str.contains('process error'))]
        error_logs = error_logs.assign(transactionDate=error_logs['transactionDate'].apply(lambda x: x if pd.notna(x) else None))
        # Assign None to the transactionDate for records with missing transactionDate

        insert_data_to_postgres("transactions", transactions, "transactionId")
        insert_data_to_postgres("customers", customers, "customerId")
        insert_data_to_postgres("error_logs", error_logs, "transactionId")


if __name__ == "__main__":
    main()
