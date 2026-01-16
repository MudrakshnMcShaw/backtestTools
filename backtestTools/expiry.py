"""\
FNO Expiry Data Module.

Provides utilities for retrieving and managing options expiry-related metadata from MongoDB.
This module handles date normalization, database queries, and expiry information lookup for
F&O (Futures and Options) contracts.
"""

import pandas as pd
from datetime import datetime
from backtestTools.histData import connectToMongo


def getExpiryData(date, sym, conn=None):
    """
    Retrieve option expiry metadata for a given date and symbol.
    
    Queries the MongoDB FNO_Expiry collection to find expiry information (current expiry date,
    strike distance, etc.) that applies to the specified trading date. Normalizes all dates to
    15:30 (market close time) before matching to ensure consistent lookups across trading days.
    
    Parameters:
        date (datetime or float): Trading date for expiry lookup. Can be:
            - datetime object: Direct datetime representation
            - float: Epoch timestamp (seconds since 1970-01-01)
            - int: Epoch timestamp (will be converted to float)
        sym (str): Base symbol for which expiry data is requested (e.g., "NIFTY50", "BANKNIFTY").
        conn (MongoClient, optional): MongoDB connection object. If None, a new connection is
            established. Default is None.
    
    Returns:
        dict: Dictionary containing expiry metadata if found, including fields such as:
            - CurrentExpiry: Nearest option expiry date for the symbol
            - StrikeDist: Strike price interval (e.g., 100 for NIFTY)
            - Other symbol-specific expiry fields from the database
        None: If no matching expiry data is found for the given date and symbol.
    
    Raises:
        Exception: If date parameter is not a datetime object, int, or float timestamp.
        Exception: Re-raises any database connection or query errors.
    """

    try:
        # Normalize input date to datetime object for consistent handling
        if isinstance(date, datetime):
            getDatetime = date
        elif isinstance(date, int):
            getDatetime = datetime.fromtimestamp(float(date))
        elif isinstance(date, float):
            getDatetime = datetime.fromtimestamp(date)
        else:
            raise Exception(
                "date is not a timestamp(float or int) or datetime object")

        expiryDict = None

        if conn is None:
            conn = connectToMongo()

        db = conn["FNO_Expiry"]
        collection = db["Data"]

        rec = collection.find({"Sym": sym})
        rec = list(rec)

        if rec:
            df = pd.DataFrame(rec)
            df["Date"] = pd.to_datetime(df["Date"])
            # Normalize all expiry dates to 15:30 (market close time) for consistent comparisons
            df["Date"] = df["Date"] + pd.Timedelta(hours=15, minutes=30)
            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True, ascending=True)

            # Find the nearest expiry date that is >= the given trading date
            # This ensures we get the correct applicable expiry for the given date
            for index, row in df.iterrows():
                if getDatetime <= index:
                    expiryDict = row.to_dict()
                    break

        return expiryDict

    except Exception as e:
        raise Exception(e)
