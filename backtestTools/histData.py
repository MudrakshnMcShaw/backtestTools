import numpy as np
import pandas as pd
from pymongo import MongoClient
from configparser import ConfigParser
from datetime import datetime, timedelta


def connectToMongo():
    """
    Connects to MongoDB database.

    Returns:
        MongoClient: A MongoDB client object representing the connection.
    """
    # Read config file
    configReader = ConfigParser()
    configReader.read("/root/backtestToolsConfig/config.ini")

    # Get MongoDB Credentials
    host = configReader.get("DBParams", "host")
    port = int(configReader.get("DBParams", "port"))
    username = configReader.get("DBParams", "username")
    password = configReader.get("DBParams", "password")

    # Connect to MongoDB Database
    try:
        conn = MongoClient(host=host, port=port,
                           username=username, password=password)
    except Exception as e:
        raise Exception(e)
    return conn


def getFnoHistData(symbol, timestamp):
    """
    Retrieves historical data for a given Fno symbol or Indices symbol and timestamp from MongoDB collection.

    Parameters:
        symbol (string): The symbol for which historical data is requested.

        timestamp (float): The timestamp for which historical data is requested.

    Returns:
        dict: A dictionary containing historical data if found, otherwise None.
    """

    try:
        conn = connectToMongo()

        db = conn["OHLC_MINUTE_1_New"]
        collection = db.Data
        rec = collection.find_one(
            {"$and": [{"sym": symbol}, {"ti": timestamp}]})

        if rec:
            return rec
        else:
            for i in range(15):
                rec = collection.find_one(
                    {"$and": [{"sym": symbol}, {"ti": timestamp + (i * 60)}]})
                if rec:
                    return rec

    except Exception as e:
        raise Exception(e)


def getFnoBacktestData(symbol, startDateTime, endDateTime, interval):
    """
    Retrieves backtest data i.e. range of data for a given Fno symbol or Indices symbol, start and end datetime, and interval.

    Parameters:
        symbol (string): The symbol for which backtest data is requested.

        startDateTime (float or datetime): The start datetime for the backtest data.

        endDateTime (float or datetime): The end datetime for the backtest data.

        interval (string): The resampling interval for the data.

    Returns:
        DataFrame: A pandas DataFrame containing resampled backtest data.
    """
    try:
        if isinstance(startDateTime, datetime) and isinstance(startDateTime, datetime):
            startTimestamp = startDateTime.timestamp()
            endTimestamp = endDateTime.timestamp()
        elif isinstance(startDateTime, int) and isinstance(startDateTime, int):
            startTimestamp = float(startDateTime)
            endTimestamp = float(endDateTime)
        elif isinstance(startDateTime, float) and isinstance(startDateTime, float):
            startTimestamp = startDateTime
            endTimestamp = endDateTime
        else:
            raise Exception(
                "startDateTime or endDateTime is not a timestamp(float or int) or datetime object")

        conn = connectToMongo()

        if interval[-1:] == "D":
            db = conn["OHLC_DAY_1"]
        else:
            db = conn["OHLC_MINUTE_1_New"]
        collection = db.Data

        rec = collection.find({"$and": [{"sym": symbol}, {
                              "ti": {"$gte": startTimestamp, "$lte": endTimestamp}},]})
        rec = list(rec)

        if rec:
            df = pd.DataFrame(rec)
            df.dropna(inplace=True)
            df.drop_duplicates(subset="ti", inplace=True)
            df.sort_values(by=["ti"], inplace=True, ascending=True)
            df.set_index("ti", inplace=True)

            df.index = pd.to_datetime(df.index, unit="s")
            df.index = df.index + timedelta(hours=5, minutes=30)

            if interval[-1:] == "D":
                df_resample = df.resample(interval).agg({
                    "o": "first",
                    "h": "max",
                    "l": "min",
                    "c": "last"
                })
            else:
                df = df.between_time("09:15:00", "15:29:00")
                df_resample = df.resample(interval, offset=pd.Timedelta(minutes=15)).agg(
                    {"o": "first",
                     "h": "max",
                     "l": "min",
                     "c": "last"}
                )

            df_resample.index = (
                df_resample.index.values.astype(np.int64) // 10**9) - 19800
            df_resample.insert(0, "ti", df_resample.index)

            df_resample.dropna(inplace=True)

            datetimeCol = pd.to_datetime(df_resample.index, unit="s")
            datetimeCol = datetimeCol + timedelta(hours=5, minutes=30)
            df_resample.insert(loc=1, column="datetime", value=datetimeCol)

            return df_resample

    except Exception as e:
        raise Exception(e)


def getEquityHistData(symbol, timestamp):
    """
    Retrieves 1-minute historical data for a given equity symbol and timestamp from MongoDB collection.

    Parameters:
        symbol (string): The symbol for which historical data is requested.

        timestamp (float): The timestamp for which historical data is requested.

    Returns:
        dict: A dictionary containing historical data if found, otherwise None.
    """
    try:
        conn = connectToMongo()

        db = conn["STOCK_MINUTE_1"]
        collection = db.Data
        rec = collection.find_one(
            {"$and": [{"sym": symbol}, {"ti": timestamp}]})

        if rec:
            return rec
        else:
            for i in range(15):
                rec = collection.find_one(
                    {"$and": [{"sym": symbol}, {"ti": timestamp + (i * 60)}]})
                if rec:
                    return rec
            raise Exception(
                f"Data not found for {symbol} at {datetime.fromtimestamp(timestamp)}")
    except Exception as e:
        raise Exception(e)


def getEquityBacktestData(symbol, startDateTime, endDateTime, interval):
    """
    Retrieves backtest data i.e. range of data for a given equity symbol, start and end datetime, and interval.

    Parameters:
        symbol (string): The symbol for which backtest data is requested.

        startDateTime (float or datetime): The start datetime for the backtest data.

        endDateTime (float or datetime): The end datetime for the backtest data.

        interval (string): The resampling interval for the data.

    Returns:
        DataFrame: A pandas DataFrame containing resampled backtest data.
    """
    try:
        if isinstance(startDateTime, datetime) and isinstance(startDateTime, datetime):
            startTimestamp = startDateTime.timestamp()
            endTimestamp = endDateTime.timestamp()
        elif isinstance(startDateTime, int) and isinstance(startDateTime, int):
            startTimestamp = float(startDateTime)
            endTimestamp = float(endDateTime)
        elif isinstance(startDateTime, float) and isinstance(startDateTime, float):
            startTimestamp = startDateTime
            endTimestamp = endDateTime
        else:
            raise Exception(
                "startDateTime or endDateTime is not a timestamp(float or int) or datetime object"
            )

        conn = connectToMongo()

        if interval[-1:] == "D":
            db = conn["STOCK_DAY_1"]
        else:
            db = conn["STOCK_MINUTE_1"]
        collection = db.Data

        rec = collection.find({"$and": [{"sym": symbol}, {
                              "ti": {"$gte": startTimestamp, "$lte": endTimestamp}},]})
        rec = list(rec)

        if rec:
            df = pd.DataFrame(rec)

            df.dropna(inplace=True)
            df.drop_duplicates(subset="ti", inplace=True)
            df.sort_values(by=["ti"], inplace=True, ascending=True)
            df.set_index("ti", inplace=True)

            df.index = pd.to_datetime(df.index, unit="s")
            df.index = df.index + timedelta(hours=5, minutes=30)

            if interval[-1:] == "D":
                df_resample = df.resample(interval).agg({
                    "o": "first",
                    "h": "max",
                    "l": "min",
                    "c": "last"
                })

            else:
                df = df.between_time("09:15:00", "15:29:00")
                df_resample = df.resample(interval, offset=pd.Timedelta(minutes=15)).agg(
                    {"o": "first",
                     "h": "max",
                     "l": "min",
                     "c": "last"}
                )

            df_resample.index = (df_resample.index.values.astype(np.int64) //
                                 10**9) - 19800
            df_resample.insert(0, "ti", df_resample.index)

            df_resample.dropna(inplace=True)

            datetimeCol = pd.to_datetime(df_resample.index, unit="s")
            datetimeCol = datetimeCol + timedelta(hours=5, minutes=30)
            df_resample.insert(loc=1, column="datetime", value=datetimeCol)

            return df_resample

    except Exception as e:
        raise Exception(e)
