import os
import numpy as np
import pandas as pd
from pymongo import MongoClient
from configparser import ConfigParser
from datetime import datetime, timedelta


def connectToMongo():
    '''
    Connects to MongoDB database.

    Returns:
        MongoClient: A MongoDB client object representing the connection.
    '''
    package_dir = os.path.dirname(__file__)
    config_path = os.path.join(package_dir, 'config.ini')

    # Read config file
    configReader = ConfigParser()
    configReader.read(config_path)

    # Get MongoDB Credentials
    host = configReader.get('DBParams', f'host')
    port = int(configReader.get('DBParams', f'port'))
    username = configReader.get('DBParams', f'username')
    password = configReader.get('DBParams', f'password')

    # Connect to MongoDB Database
    try:
        conn = MongoClient(
            host=host, port=port, username=username, password=password)
    except Exception as e:
        raise Exception(e)
    return conn


def getFnoHistData(symbol, timestamp):
    '''
    Retrieves historical data for a given Fno symbol or Indices symbol and timestamp from MongoDB collection.

    Parameters:
        symbol (string): The symbol for which historical data is requested.

        timestamp (float): The timestamp for which historical data is requested.

    Returns:
        dict: A dictionary containing historical data if found, otherwise None.
    '''
    try:
        conn = connectToMongo()

        db = conn['OHLC_MINUTE_1_New']
        collection = db.Data
        rec = collection.find_one(
            {'$and': [{'sym': symbol},
                      {"ti": timestamp}]})

        if rec:
            return rec
        else:
            for i in range(15):
                rec = collection.find_one(
                    {'$and': [{'sym': symbol},
                              {"ti": timestamp + (i*60)}]})
                if rec:
                    return rec

            '''Checking another collection if data not found'''

            db = conn['testing']
            collection = db["FNO_OHLC_1min"]
            rec = collection.find_one(
                {'$and': [{'sym': symbol},
                          {"ti": timestamp}]})

            if rec:
                return rec
            else:
                for i in range(15):
                    rec = collection.find_one(
                        {'$and': [{'sym': symbol},
                                  {"ti": timestamp + (i*60)}]})
                    if rec:
                        return rec

            '''If not found raise exception'''
            raise Exception(
                f"Data not found for {symbol} at {datetime.fromtimestamp(timestamp+(i*60))}")
    except Exception as e:
        raise Exception(e)


def getFnoBacktestData(symbol, startDateTime, endDateTime, interval):
    '''
    Retrieves backtest data i.e. range of data for a given Fno symbol or Indices symbol, start and end datetime, and interval.

    Parameters:
        symbol (string): The symbol for which backtest data is requested.

        startDateTime (float or datetime): The start datetime for the backtest data.

        endDateTime (float or datetime): The end datetime for the backtest data.

        interval (string): The resampling interval for the data.

    Returns:
        DataFrame: A pandas DataFrame containing resampled backtest data.
    '''
    try:
        if isinstance(startDateTime, datetime) and isinstance(startDateTime, datetime):
            startTimestamp = startDateTime.timestamp()
            endTimestamp = endDateTime.timestamp()
        elif isinstance(startDateTime, float) and isinstance(startDateTime, float):
            startTimestamp = startDateTime
            endTimestamp = endDateTime
        else:
            raise Exception(
                "startDateTime or endDateTime is not a timestamp(float) or datetime object")

        conn = connectToMongo()

        db = conn["OHLC_MINUTE_1_New"]
        collection = db.Data

        rec = collection.find(
            {'$and': [{'sym': symbol}, {"ti": {'$gte': startTimestamp, '$lte': endTimestamp}}]})

        rec = list(rec)
        if rec:
            df = pd.DataFrame(rec)
            df.drop_duplicates(subset="ti", inplace=True)
            # df.reset_index(drop=True, inplace=True)
            df.sort_values(by=["ti"], inplace=True, ascending=True)
            df.dropna(inplace=True)
            df.set_index("ti", inplace=True)

            df.index = pd.to_datetime(df.index, unit='s')
            df.index = df.index + timedelta(hours=5, minutes=30)
            df = df.between_time('09:15:00', '15:29:00')

            df_resample = df.resample(interval).agg({
                'o': 'first',
                'h': 'max',
                'l': 'min',
                'c': 'last'
            })
            df_resample.index = (df_resample.index.values.astype(
                np.int64) // 10 ** 9) - 19800

            return df_resample

        '''Checking another collection if data not found'''
        if not rec:
            db = conn["testing"]
            collection = db["FNO_OHLC_1min"]

            rec = collection.find(
                {'$and': [{'sym': symbol}, {"ti": {'$gte': startTimestamp, '$lte': endTimestamp}}]})

            rec = list(rec)
            if rec:
                df = pd.DataFrame(rec)

                df.drop_duplicates(subset="ti", inplace=True)
                df.sort_values(by=["ti"], inplace=True, ascending=True)
                df.dropna(inplace=True)
                df.set_index("ti", inplace=True)

                df.index = pd.to_datetime(df.index, unit='s')
                df.index = df.index + timedelta(hours=5, minutes=30)
                df = df.between_time('09:15:00', '15:29:00')

                df_resample = df.resample(interval).agg({
                    'o': 'first',
                    'h': 'max',
                    'l': 'min',
                    'c': 'last'
                })

                df_resample["ti"] = df_resample["ti"].timestamp() - 19800
                return df_resample
    except Exception as e:
        raise Exception(e)


def getEquityHistData(symbol, timestamp):
    '''
    Retrieves historical data for a given equity symbol and timestamp from MongoDB collection.

    Parameters:
        symbol (string): The symbol for which historical data is requested.

        timestamp (float): The timestamp for which historical data is requested.

    Returns:
        dict: A dictionary containing historical data if found, otherwise None.
    '''
    try:
        conn = connectToMongo()

        db = conn['STOCK_DAY_1']
        collection = db.Data
        rec = collection.find_one(
            {'$and': [{'sym': symbol},
                      {"ti": timestamp}]})

        if rec:
            return rec
        else:
            raise Exception(
                f"Data not found for {symbol} at {datetime.fromtimestamp(timestamp)}")
    except Exception as e:
        raise Exception(e)


def getEquityBacktestData(symbol, startDateTime, endDateTime):
    '''
    Retrieves backtest data i.e. range of data for a given equity symbol, start and end datetime, and interval.

    Parameters:
        symbol (string): The symbol for which backtest data is requested.

        startDateTime (float or datetime): The start datetime for the backtest data.

        endDateTime (float or datetime): The end datetime for the backtest data.

        interval (string): The resampling interval for the data.

    Returns:
        DataFrame: A pandas DataFrame containing resampled backtest data.
    '''
    try:
        if isinstance(startDateTime, datetime) and isinstance(startDateTime, datetime):
            startTimestamp = startDateTime.timestamp()
            endTimestamp = endDateTime.timestamp()
        elif isinstance(startDateTime, float) and isinstance(startDateTime, float):
            startTimestamp = startDateTime
            endTimestamp = endDateTime
        else:
            raise Exception(
                "startDateTime or endDateTime is not a timestamp(float) or datetime object")

        conn = connectToMongo()

        db = conn["STOCK_DAY_1"]
        collection = db.Data

        rec = collection.find(
            {'$and': [{'sym': symbol}, {"ti": {'$gte': startTimestamp, '$lte': endTimestamp}}]})

        if rec:
            df = pd.DataFrame(list(rec))

            df.drop_duplicates(subset="ti", inplace=True)
            df["ti"] = df["ti"] + 33300  # Adjust 1-day data timestamps
            df.sort_values(by=["ti"], inplace=True, ascending=True)
            df.dropna(inplace=True)
            df.set_index("ti", inplace=True)

            return df
    except Exception as e:
        raise Exception(e)
