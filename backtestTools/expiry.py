import pandas as pd
from datetime import datetime
from backtestTools.histData import connectToMongo


def getExpiryData(date, sym, conn=None):
    """
    Retrieves expiry data for a given date and symbol from MongoDB collections.

    Parameters:
        date (datetime or float): The date for which expiry data is requested. It can be either a datetime object or a timestamp in float format.

        sym (string): The base symbol for which expiry data is requested.

    Returns:
        dictionary: A dictionary containing expiry data if found, otherwise None.
    """

    try:
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
            df["Date"] = df["Date"] + pd.Timedelta(hours=15, minutes=30)
            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True, ascending=True)

            for index, row in df.iterrows():
                if getDatetime <= index:
                    expiryDict = row.to_dict()
                    break

        return expiryDict

    except Exception as e:
        raise Exception(e)
