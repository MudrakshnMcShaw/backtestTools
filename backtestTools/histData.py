"""
Historical Data Retrieval Module.

Provides utilities for connecting to MongoDB and retrieving historical OHLC (Open, High, Low, Close)
data for both F&O (Futures and Options) and equity instruments. Supports single point-in-time lookups
and range-based backtest data retrieval with automatic resampling to specified intervals.

Data Sources:
    - OHLC_MINUTE_1_New: F&O minute-level data
    - OHLC_DAY_1: F&O daily data
    - STOCK_MINUTE_1: Equity minute-level data
    - STOCK_DAY_1: Equity daily data

Functions:
    connectToMongo: Establishes MongoDB connection using credentials from config file.
    getFnoHistData: Retrieves single F&O data point for a given timestamp.
    getFnoBacktestData: Retrieves and resamples F&O data range for backtesting.
    getEquityHistData: Retrieves single equity data point for a given timestamp.
    getEquityBacktestData: Retrieves and resamples equity data range for backtesting.
"""

import numpy as np
import pandas as pd
from pymongo import MongoClient
from configparser import ConfigParser
from datetime import datetime, timedelta


def connectToMongo():
    """
    Establish MongoDB connection using credentials from configuration file.
    
    Reads MongoDB connection parameters (host, port, username, password) from the system
    configuration file located at /root/backtestToolsConfig/config.ini and establishes
    an authenticated connection to the MongoDB instance.
    
    Returns:
        MongoClient: Connected MongoDB client object ready for database operations.
    
    Raises:
        Exception: If configuration file is missing, credentials are invalid, or connection
            to MongoDB fails.
    """
    configReader = ConfigParser()
    configReader.read("/root/backtestToolsConfig/config.ini")

    host = configReader.get("DBParams", "host")
    port = int(configReader.get("DBParams", "port"))
    username = configReader.get("DBParams", "username")
    password = configReader.get("DBParams", "password")

    try:
        conn = MongoClient(host=host, port=port,
                           username=username, password=password)
    except Exception as e:
        raise Exception(e)
    return conn


def getFnoHistData(symbol, timestamp, conn=None):
    """
    Retrieve single F&O data point at exact or near timestamp.
    
    Queries the MongoDB OHLC_MINUTE_1_New collection for a single minute OHLC bar at the specified
    timestamp. If exact timestamp is unavailable, attempts to find the nearest available data point
    within the next 15 minutes (searches up to 14 additional timestamps at 60-second intervals).
    
    Parameters:
        symbol (str): F&O symbol or index symbol to retrieve data for (e.g., "NIFTY50", "BANKNIFTY").
        timestamp (float): Epoch timestamp (seconds since 1970-01-01) for the requested data point.
        conn (MongoClient, optional): MongoDB connection object. If None, a new connection is
            established. Default is None.
    
    Returns:
        dict: Dictionary containing OHLC data and metadata if found, with keys typically including:
            - sym: Symbol
            - ti: Timestamp
            - o: Open price
            - h: High price
            - l: Low price
            - c: Close price
            - v: Volume
            - oi: Open Interest
        None: If no data is found at the timestamp or within 15-minute search window.
    
    Raises:
        Exception: If MongoDB connection fails or query errors occur.
    """

    try:
        if conn is None:
            conn = connectToMongo()

        db = conn["OHLC_MINUTE_1_New"]
        collection = db.Data
        rec = collection.find_one(
            {"$and": [{"sym": symbol}, {"ti": timestamp}]})

        if rec:
            return rec
        else:
            # Search up to 15 minutes forward if exact timestamp not found
            # This handles cases where market data may not align exactly with requested timestamp
            for i in range(15):
                rec = collection.find_one(
                    {"$and": [{"sym": symbol}, {"ti": timestamp + (i * 60)}]})
                if rec:
                    return rec

    except Exception as e:
        raise Exception(e)


def getFnoBacktestData(symbol, startDateTime, endDateTime, interval, conn=None):
    """
    Retrieve and resample F&O data range for backtesting.
    
    Fetches all OHLC data for the specified symbol within the date range and resamples it to the
    requested interval (e.g., "1Min", "5Min", "1D"). Handles minute-level data (09:15-15:29) and
    daily data differently. Converts timestamps to IST (UTC+5:30) and removes duplicates and NaN values.
    
    Parameters:
        symbol (str): F&O symbol or index symbol (e.g., "NIFTY50", "BANKNIFTY").
        startDateTime (datetime, int, or float): Start of data range. Can be:
            - datetime object: Direct datetime representation
            - int: Epoch timestamp (seconds)
            - float: Epoch timestamp (seconds)
        endDateTime (datetime, int, or float): End of data range. Can be:
            - datetime object: Direct datetime representation
            - int: Epoch timestamp (seconds)
            - float: Epoch timestamp (seconds)
        interval (str): Resampling interval for output data. Examples:
            - "1Min": 1-minute bars (market hours only: 09:15-15:29)
            - "5Min": 5-minute bars
            - "1H": 1-hour bars
            - "1D": Daily bars
        conn (MongoClient, optional): MongoDB connection object. If None, a new connection is
            established. Default is None.
    
    Returns:
        pd.DataFrame: DataFrame with resampled OHLC data indexed by epoch timestamp (IST-normalized),
            containing columns:
            - ti: Epoch timestamp (IST-adjusted)
            - datetime: Human-readable datetime (IST)
            - o: Open price (first value in period)
            - h: High price (maximum in period)
            - l: Low price (minimum in period)
            - c: Close price (last value in period)
            - v: Volume (sum in period)
            - oi: Open Interest (sum in period)
    
    Raises:
        Exception: If startDateTime/endDateTime types are invalid (must be datetime, int, or float).
        Exception: If MongoDB connection fails or query errors occur.
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

        if conn is None:
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

            # Fill missing OHLC values with 0 to prevent resampling errors
            if 'oi' in df.columns:
                df['oi'] = df["oi"].fillna(0)
            else:
                df['oi'] = 0

            if 'v' in df.columns:
                df['v'] = df["v"].fillna(0)
            else:
                df['v'] = 0

            if 'date' in df.columns:
                df['date'] = df["date"].fillna(pd.to_datetime(df["ti"]))

            df.drop_duplicates(subset="ti", inplace=True)
            df.sort_values(by=["ti"], inplace=True, ascending=True)
            df.set_index("ti", inplace=True)

            # Convert timestamps from UTC to IST (UTC+5:30) for Indian market
            df.index = pd.to_datetime(df.index, unit="s")
            df.index = df.index + timedelta(hours=5, minutes=30)

            # Aggregate data differently for daily vs. intraday intervals
            if interval[-1:] == "D":
                df_resample = df.resample(interval).agg({
                    "o": "first",
                    "h": "max",
                    "l": "min",
                    "c": "last",
                    "v": "sum",
                    "oi": "sum",
                })
            else:
                # For minute intervals, filter to market hours (09:15-15:29) before resampling
                # This prevents off-market data from contaminating the bars
                df = df.between_time("09:15:00", "15:29:00")
                df_resample = df.resample(interval, origin="9:15").agg(
                    {"o": "first",
                     "h": "max",
                     "l": "min",
                     "c": "last",
                     "v": "sum",
                     "oi": "sum", }
                )

            # Convert resampled timestamps back to UTC (epoch) adjusted for IST offset (19800 seconds)
            df_resample.index = (
                df_resample.index.values.astype(np.int64) // 10**9) - 19800
            df_resample.insert(0, "ti", df_resample.index)

            df_resample.dropna(inplace=True)

            # Add human-readable datetime column in IST
            datetimeCol = pd.to_datetime(df_resample.index, unit="s")
            datetimeCol = datetimeCol + timedelta(hours=5, minutes=30)
            df_resample.insert(loc=1, column="datetime", value=datetimeCol)

            return df_resample

    except Exception as e:
        raise Exception(e)


def getEquityHistData(symbol, timestamp, conn=None):
    """
    Retrieve single equity data point at exact or near timestamp.
    
    Queries the MongoDB STOCK_MINUTE_1 collection for a single minute OHLC bar at the specified
    timestamp. If exact timestamp is unavailable, attempts to find the nearest available data point
    within the next 15 minutes (searches up to 14 additional timestamps at 60-second intervals).
    
    Parameters:
        symbol (str): Equity stock symbol (e.g., "RELIANCE", "INFY").
        timestamp (float): Epoch timestamp (seconds since 1970-01-01) for the requested data point.
        conn (MongoClient, optional): MongoDB connection object. If None, a new connection is
            established. Default is None.
    
    Returns:
        dict: Dictionary containing OHLC data and metadata if found, with keys typically including:
            - sym: Symbol
            - ti: Timestamp
            - o: Open price
            - h: High price
            - l: Low price
            - c: Close price
            - v: Volume
    
    Raises:
        Exception: If no data is found for the symbol at the timestamp or within 15-minute window.
        Exception: If MongoDB connection fails or query errors occur.
    """
    try:
        if conn is None:
            conn = connectToMongo()

        db = conn["STOCK_MINUTE_1"]
        collection = db.Data
        rec = collection.find_one(
            {"$and": [{"sym": symbol}, {"ti": timestamp}]})

        if rec:
            return rec
        else:
            # Search up to 15 minutes forward if exact timestamp not found
            # This handles cases where market data may not align exactly with requested timestamp
            for i in range(15):
                rec = collection.find_one(
                    {"$and": [{"sym": symbol}, {"ti": timestamp + (i * 60)}]})
                if rec:
                    return rec
            # Equity data missing entirely (stricter than F&O which returns None)
            raise Exception(
                f"Data not found for {symbol} at {datetime.fromtimestamp(timestamp)}")
    except Exception as e:
        raise Exception(e)


def getEquityBacktestData(symbol, startDateTime, endDateTime, interval, conn=None):
    """
    Retrieve and resample equity data range for backtesting.
    
    Fetches all OHLC data for the specified equity within the date range and resamples it to the
    requested interval (e.g., "1Min", "5Min", "1D"). Handles minute-level data (09:15-15:29) and
    daily data differently. Converts timestamps to IST (UTC+5:30) and removes duplicates and NaN values.
    
    Parameters:
        symbol (str): Equity stock symbol (e.g., "RELIANCE", "INFY").
        startDateTime (datetime, int, or float): Start of data range. Can be:
            - datetime object: Direct datetime representation
            - int: Epoch timestamp (seconds)
            - float: Epoch timestamp (seconds)
        endDateTime (datetime, int, or float): End of data range. Can be:
            - datetime object: Direct datetime representation
            - int: Epoch timestamp (seconds)
            - float: Epoch timestamp (seconds)
        interval (str): Resampling interval for output data. Examples:
            - "1Min": 1-minute bars (market hours only: 09:15-15:29)
            - "5Min": 5-minute bars
            - "1H": 1-hour bars
            - "1D": Daily bars
        conn (MongoClient, optional): MongoDB connection object. If None, a new connection is
            established. Default is None.
    
    Returns:
        pd.DataFrame: DataFrame with resampled OHLC data indexed by epoch timestamp (IST-normalized),
            containing columns:
            - ti: Epoch timestamp (IST-adjusted)
            - datetime: Human-readable datetime (IST)
            - o: Open price (first value in period)
            - h: High price (maximum in period)
            - l: Low price (minimum in period)
            - c: Close price (last value in period)
            - v: Volume (sum in period)
            - oi: Open Interest (sum in period)
    
    Raises:
        Exception: If startDateTime/endDateTime types are invalid (must be datetime, int, or float).
        Exception: If MongoDB connection fails or query errors occur.
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

        if conn is None:
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

            # Fill missing OHLC values with 0 to prevent resampling errors
            if 'oi' in df.columns:
                df['oi'] = df["oi"].fillna(0)
            else:
                df['oi'] = 0

            if 'v' in df.columns:
                df['v'] = df["v"].fillna(0)
            else:
                df['v'] = 0

            if 'date' in df.columns:
                df['date'] = df["date"].fillna(pd.to_datetime(df["ti"]))

            df.drop_duplicates(subset="ti", inplace=True)
            df.sort_values(by=["ti"], inplace=True, ascending=True)
            df.set_index("ti", inplace=True)

            # Convert timestamps from UTC to IST (UTC+5:30) for Indian market
            df.index = pd.to_datetime(df.index, unit="s")
            df.index = df.index + timedelta(hours=5, minutes=30)

            # Aggregate data differently for daily vs. intraday intervals
            if interval[-1:] == "D":
                df_resample = df.resample(interval).agg({
                    "o": "first",
                    "h": "max",
                    "l": "min",
                    "c": "last",
                    "v": "sum",
                    "oi": "sum",
                })

            else:
                # For minute intervals, filter to market hours (09:15-15:29) before resampling
                # This prevents off-market data from contaminating the bars
                df = df.between_time("09:15:00", "15:29:00")
                df_resample = df.resample(interval, origin="9:15").agg(
                    {"o": "first",
                     "h": "max",
                     "l": "min",
                     "c": "last",
                     "v": "sum",
                     "oi": "sum", }
                )

            # Convert resampled timestamps back to UTC (epoch) adjusted for IST offset (19800 seconds)
            df_resample.index = (df_resample.index.values.astype(np.int64) //
                                 10**9) - 19800
            df_resample.insert(0, "ti", df_resample.index)

            df_resample.dropna(inplace=True)

            # Add human-readable datetime column in IST
            datetimeCol = pd.to_datetime(df_resample.index, unit="s")
            datetimeCol = datetimeCol + timedelta(hours=5, minutes=30)
            df_resample.insert(loc=1, column="datetime", value=datetimeCol)

            return df_resample

    except Exception as e:
        raise Exception(e)
