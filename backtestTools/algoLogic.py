"""\
Backtest Algorithm Logic Module.

This module provides foundational classes for implementing algorithmic trading strategies.
It includes base logic for managing trades, calculating profit and loss (PnL), handling data
storage, and specialized classes for options trading (both intraday and overnight) and equity
trading strategies. The module integrates with MongoDB for data retrieval and supports both
F&O (Futures and Options) and equity instruments.

Classes:
    baseAlgoLogic: Base class for all trading algorithms with trade management and PnL tracking.
    optAlgoLogic: Options-specific trading logic with strike price and expiry management.
    optIntraDayAlgoLogic: Specialized options trading for intraday strategies.
    optOverNightAlgoLogic: Specialized options trading for overnight strategies.
    equityOverNightAlgoLogic: Specialized equity trading for overnight strategies.
    equityIntradayAlgoLogic: Specialized equity trading for intraday strategies.
"""

import os
import glob
import pandas as pd
from datetime import datetime
from backtestTools.histData import connectToMongo, getFnoBacktestData
from backtestTools.util import setup_logger


class baseAlgoLogic:
    """
    Base class for implementing algorithmic trading logic.
    
    Provides methods for managing trades, calculating profit and loss (PnL), and handling data storage.
    This class serves as the foundation for all specific algorithmic trading strategies (options, equity, etc.).
    It manages trade entries and exits, tracks both realized and unrealized PnL, and persists results to CSV files.
    
    Attributes:
        devName (str): Developer name associated with the strategy.
        strategyName (str): Name of the trading strategy.
        version (str): Version identifier for the strategy.
        conn (MongoClient): MongoDB connection object for data retrieval. Initialized in __init__.
        timeData (float): Current timestamp in epoch format.
        humanTime (datetime): Current datetime as a Python datetime object.
        unrealizedPnl (float): Profit/loss from currently open positions.
        realizedPnl (float): Profit/loss from closed positions.
        netPnl (float): Total PnL combining realized and unrealized components.
        openPnl (pd.DataFrame): DataFrame storing open trade positions with columns:
            EntryTime, Symbol, EntryPrice, CurrentPrice, Quantity, PositionStatus, Pnl.
        closedPnl (pd.DataFrame): DataFrame storing closed trade positions with columns:
            Key, ExitTime, Symbol, EntryPrice, ExitPrice, Quantity, PositionStatus, Pnl, ExitType.
        fileDir (dict): Dictionary containing file paths for result storage.
        fileDirUid (int): Unique identifier for this backtest run.
        strategyLogger (logging.Logger): Logger instance for strategy execution logs.
    """

    def __init__(self, devName, strategyName, version):
        """
        Initialize a baseAlgoLogic instance with strategy metadata and result directories.
        
        Creates directory structure for storing backtest results, initializes DataFrames for trade tracking,
        establishes MongoDB connection, and sets up logging. Automatically generates unique UIDs for each
        backtest run to avoid result overwrites.
        
        Parameters:
            devName (str): Developer name associated with the strategy.
            strategyName (str): Name of the trading strategy.
            version (str): Version identifier for the strategy.
        """

        self.devName = devName
        self.strategyName = strategyName
        self.version = version

        self.conn = connectToMongo()
        self.timeData = 0
        self.humanTime = datetime.fromtimestamp(0)

        self.unrealizedPnl = 0
        self.realizedPnl = 0
        self.netPnl = 0

        self.openPnl = pd.DataFrame(columns=[
                                    "EntryTime", "Symbol", "EntryPrice", "CurrentPrice", "Quantity", "PositionStatus", "Pnl",])
        self.closedPnl = pd.DataFrame(columns=[
                                      "Key", "ExitTime", "Symbol", "EntryPrice", "ExitPrice", "Quantity", "PositionStatus", "Pnl", "ExitType",])

        self.fileDir = {
            "backtestResults": "BacktestResults/",
            "backtestResultsStrategy": f"BacktestResults/{self.devName}_{self.strategyName}_{self.version}/",
        }
        for dirs in self.fileDir.values():
            if not os.path.exists(dirs):
                os.makedirs(dirs)

        folder_names = []
        for item in os.listdir(self.fileDir["backtestResultsStrategy"]):
            item_path = os.path.join(self.fileDir["backtestResultsStrategy"],
                                     item)
            if os.path.isdir(item_path):
                folder_names.append(int(item))

        self.fileDirUid = (max(folder_names) + 1) if folder_names else 1
        self.fileDir["backtestResultsStrategyUid"] = (
            f"{self.fileDir['backtestResultsStrategy']}{self.fileDirUid}/")
        self.fileDir["backtestResultsOpenPnl"] = (
            f"{self.fileDir['backtestResultsStrategyUid']}OpenPnlCsv/")
        self.fileDir["backtestResultsClosePnl"] = (
            f"{self.fileDir['backtestResultsStrategyUid']}ClosePnlCsv/")
        self.fileDir["backtestResultsCandleData"] = (
            f"{self.fileDir['backtestResultsStrategyUid']}CandleData/")
        self.fileDir["backtestResultsStrategyLogs"] = (
            f"{self.fileDir['backtestResultsStrategyUid']}StrategyLogs/")
        for dirs in self.fileDir.values():
            if not os.path.exists(dirs):
                os.makedirs(dirs)

        # logging.basicConfig(level=logging.DEBUG,
        #                     filename=f"{self.fileDir['backtestResultsStrategyLogs']}/backTest.log", filemode='w', force=True)
        # logging.info("----------New Start----------")
        # logging.propagate = False
        self.strategyLogger = setup_logger(
            "strategyLogger", f"{self.fileDir['backtestResultsStrategyLogs']}/backTest.log",)
        self.strategyLogger.propagate = False

    def addColumnsToOpenPnlDf(self, columns):
        """
        Add multiple new columns to the openPnl DataFrame.
        
        Allows dynamic extension of the openPnl DataFrame schema to store strategy-specific trade attributes
        beyond the default columns.
        
        Parameters:
            columns (list): List of column names (strings) to be added to the DataFrame.
        
        Returns:
            None
        """

        for col in columns:
            self.openPnl[col] = None

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None):
        """
        Record a trade entry order and add it to the openPnl DataFrame.
        
        Creates a new row in the openPnl DataFrame with the entry details. Converts BUY/SELL position
        status to numeric values (+1/-1) for easier PnL calculations. Logs the entry order execution.
        
        Parameters:
            entryPrice (float): Entry price of the asset.
            symbol (str): Trading symbol/ticker of the asset.
            quantity (int): Number of units/contracts being traded.
            positionStatus (str): Position direction, either "BUY" or "SELL".
            extraColDict (dict, optional): Dictionary of additional custom columns to store with the trade.
                Default is None.
        
        Returns:
            None
        """
        if self.openPnl.empty:
            index = 0
        else:
            index = self.openPnl.index[-1] + 1

        self.openPnl.at[index, "EntryTime"] = self.humanTime
        self.openPnl.at[index, "Symbol"] = symbol
        self.openPnl.at[index, "EntryPrice"] = entryPrice
        self.openPnl.at[index, "CurrentPrice"] = entryPrice
        self.openPnl.at[index, "Quantity"] = quantity
        self.openPnl.at[index,
                        "PositionStatus"] = 1 if positionStatus == "BUY" else -1
        self.openPnl.at[index, "Pnl"] = 0

        if extraColDict:
            for key, value in extraColDict.items():
                self.openPnl.at[index, key] = value

        self.strategyLogger.info(
            f"Datetime: {self.humanTime}\t {positionStatus} Entry Order of {symbol} executed at {entryPrice}"
        )

    def exitOrder(self, index, exitType, exitPrice=None):
        """
        Record a trade exit order and move it from openPnl to closedPnl DataFrame.
        
        Retrieves the trade from openPnl at the specified index, calculates realized PnL,
        and transfers the complete trade record to closedPnl with exit details. Logs the exit
        order execution.
        
        Parameters:
            index (int): Index of the trade in the openPnl DataFrame to be closed.
            exitType (str): Classification of the exit (e.g., "StopLoss", "TakeProfit", "Manual").
            exitPrice (float, optional): Exit price of the trade. If None, uses CurrentPrice from openPnl.
                Default is None.
        
        Returns:
            None
        """
        trade_to_close = self.openPnl.loc[index].to_frame().T

        self.openPnl.drop(index=index, inplace=True)

        trade_to_close.at[index, "Key"] = trade_to_close.at[index, "EntryTime"]
        trade_to_close.at[index, "ExitTime"] = self.humanTime
        trade_to_close.at[index, "ExitPrice"] = (
            trade_to_close.at[index, "CurrentPrice"] if not exitPrice else exitPrice)
        trade_to_close.at[index, "Pnl"] = ((trade_to_close.at[index, "ExitPrice"] - trade_to_close.at[index, "EntryPrice"])
                                           * trade_to_close.at[index, "Quantity"] * trade_to_close.at[index, "PositionStatus"])
        trade_to_close.at[index, "ExitType"] = exitType

        self.closedPnl.loc[len(self.closedPnl)] = trade_to_close.drop(columns=[
            col for col in self.openPnl.columns if col not in self.closedPnl.columns]).iloc[0]

        self.strategyLogger.info(
            f"Datetime: {self.humanTime}\t Exit Order of {trade_to_close.at[index, 'Symbol']} executed at {trade_to_close.at[index, 'ExitPrice']}")

    def pnlCalculator(self):
        """
        Calculate and update realized, unrealized, and net profit and loss.
        
        Iterates through open trades to compute unrealized PnL based on current prices,
        sums realized PnL from closed trades, and computes total net PnL. Updates instance
        attributes unrealizedPnl, realizedPnl, and netPnl accordingly.
        
        Returns:
            None
        """
        # Calculate unrealized PnL from open trades
        if not self.openPnl.empty:
            self.openPnl["Pnl"] = ((self.openPnl["CurrentPrice"] - self.openPnl["EntryPrice"])
                                   * self.openPnl["Quantity"] * self.openPnl["PositionStatus"])
            self.unrealizedPnl = self.openPnl["Pnl"].sum()
        else:
            self.unrealizedPnl = 0

        # Calculate realized PnL from closed trades
        if not self.closedPnl.empty:
            self.realizedPnl = self.closedPnl["Pnl"].sum()
        else:
            self.realizedPnl = 0

        # Calculate net PnL by adding realized and unrealized PnLs
        self.netPnl = self.unrealizedPnl + self.realizedPnl

    def combinePnlCsv(self):
        """
        Aggregate all openPnl and closedPnl CSV files and save consolidated results.
        
        Reads all individual CSV files from the openPnl and closedPnl directories,
        concatenates them into single DataFrames, removes index columns, sorts by timestamp,
        and saves the aggregated results as consolidated CSV files.
        
        Returns:
            pd.DataFrame: Combined DataFrame of all closed trades with columns:
                Key, ExitTime, Symbol, EntryPrice, ExitPrice, Quantity, PositionStatus, Pnl, ExitType.
        """
        openPnl = pd.DataFrame(columns=[
                               "EntryTime", "Symbol", "EntryPrice", "CurrentPrice", "Quantity", "PositionStatus", "Pnl"])
        closedPnl = pd.DataFrame(columns=["Key", "ExitTime", "Symbol", "EntryPrice",
                                 "ExitPrice", "Quantity", "PositionStatus", "Pnl", "ExitType"])

        openCsvFiles = glob.glob(os.path.join(
            self.fileDir["backtestResultsOpenPnl"], "*.csv"))
        openPnl = pd.concat([openPnl] + [pd.read_csv(csvFile)
                            for csvFile in openCsvFiles])

        closeCsvFiles = glob.glob(os.path.join(
            self.fileDir["backtestResultsClosePnl"], "*.csv"))
        closedPnl = pd.concat([closedPnl] + [pd.read_csv(csvFile)
                              for csvFile in closeCsvFiles])

        openPnl["EntryTime"] = pd.to_datetime(openPnl["EntryTime"])
        openPnl = openPnl.drop(columns=["Unnamed: 0"] if "Unnamed: 0" in openPnl.columns else [
        ]).sort_values(by=["EntryTime"]).reset_index(drop=True)

        closedPnl["Key"] = pd.to_datetime(closedPnl["Key"])
        closedPnl["ExitTime"] = pd.to_datetime(closedPnl["ExitTime"])
        closedPnl = closedPnl.drop(columns=["Unnamed: 0"] if "Unnamed: 0" in closedPnl.columns else [
        ]).sort_values(by=["Key"]).reset_index(drop=True)

        openPnl.to_csv(
            f"{self.fileDir['backtestResultsStrategyUid']}openPnl_{self.devName}_{self.strategyName}_{self.version}_{self.fileDirUid}.csv", index=False)
        self.strategyLogger.info("OpenPNL.csv saved.")

        closedPnl.to_csv(
            f"{self.fileDir['backtestResultsStrategyUid']}closePnl_{self.devName}_{self.strategyName}_{self.version}_{self.fileDirUid}.csv", index=False)
        self.strategyLogger.info("ClosePNL.csv saved.")

        return closedPnl


class optAlgoLogic(baseAlgoLogic):
    """
    Options-specific algorithmic trading logic.
    
    Extends baseAlgoLogic with functionality for options trading including dynamic strike price
    calculation, expiry management, and caching mechanisms for efficient data retrieval. Supports
    both call and put option symbol generation based on current market prices and technical parameters.
    
    Inherits:
        All attributes and methods from baseAlgoLogic.
    
    Attributes:
        symbolDataCache (dict): In-memory cache for F&O symbol historical data keyed by symbol.
            Automatically evicts expired contracts to manage memory usage.
        expiryDataCache (dict): In-memory cache for option expiry information keyed by base symbol.
            Indexed by datetime for efficient lookups.
    """

    def __init__(self, devName, strategyName, version):
        super().__init__(devName, strategyName, version)
        self.symbolDataCache = {}
        self.expiryDataCache = {}

    def getCallSym(self, date, baseSym, indexPrice, expiry=None, otmFactor=0, strikeDist=None, conn=None):
        """
        Generate a call option symbol with strike price based on current index price.
        
        Calculates the at-the-money (ATM) strike by rounding the index price to the nearest
        strike distance, then applies the OTM factor to generate out-of-the-money strikes.
        Automatically determines the nearest available expiry if not specified.
        
        Parameters:
            date (datetime or float): Reference date for determining option expiry.
                Can be datetime object or epoch timestamp (int/float).
            baseSym (str): Base symbol of the underlying asset (e.g., "NIFTY50", "BANKNIFTY").
            indexPrice (float): Current market price of the underlying asset.
            expiry (str, optional): Specific expiry date string to use (e.g., "27MAR25").
                If None, uses the nearest available expiry. Default is None.
            otmFactor (int, optional): Number of strikes above ATM to generate.
                E.g., otmFactor=1 generates strike at ATM + strikeDistance. Default is 0 (ATM).
            strikeDist (float, optional): Strike price interval (e.g., 100 for NIFTY). 
                If None, retrieved from expiry data. Default is None.
            conn (MongoClient, optional): MongoDB connection for data retrieval.
                If None, a new connection is established. Default is None.
        
        Returns:
            str: Call option symbol with expiry and strike (e.g., "NIFTY27MAR2526000CE").
        """
        if isinstance(date, datetime):
            dateEpoch = date.timestamp()
        elif isinstance(date, int):
            dateEpoch = float(date)
        elif isinstance(date, float):
            dateEpoch = date
        else:
            raise Exception(
                "date is not a timestamp(float or int) or datetime object")

        if conn is None:
            conn = connectToMongo()

        expiryData = self.fetchAndCacheExpiryData(dateEpoch, baseSym, conn)

        if expiry is None:
            symWithExpiry = baseSym + expiryData["CurrentExpiry"]
        else:
            symWithExpiry = baseSym + expiry

        if strikeDist is None:
            strikeDist = expiryData["StrikeDist"]

        remainder = indexPrice % strikeDist
        atm = (indexPrice - remainder if remainder <= (strikeDist / 2)
               else (indexPrice - remainder + strikeDist))

        callSym = (symWithExpiry + str(int(atm) +
                   (otmFactor * int(strikeDist))) + "CE")

        return callSym

    def getPutSym(self, date, baseSym, indexPrice, expiry=None, otmFactor=0, strikeDist=None, conn=None):
        """
        Generate a put option symbol with strike price based on current index price.
        
        Calculates the at-the-money (ATM) strike by rounding the index price to the nearest
        strike distance, then applies the OTM factor to generate out-of-the-money strikes below ATM.
        Automatically determines the nearest available expiry if not specified.
        
        Parameters:
            date (datetime or float): Reference date for determining option expiry.
                Can be datetime object or epoch timestamp (int/float).
            baseSym (str): Base symbol of the underlying asset (e.g., "NIFTY50", "BANKNIFTY").
            indexPrice (float): Current market price of the underlying asset.
            expiry (str, optional): Specific expiry date string to use (e.g., "27MAR25").
                If None, uses the nearest available expiry. Default is None.
            otmFactor (int, optional): Number of strikes below ATM to generate.
                E.g., otmFactor=1 generates strike at ATM - strikeDistance. Default is 0 (ATM).
            strikeDist (float, optional): Strike price interval (e.g., 100 for NIFTY).
                If None, retrieved from expiry data. Default is None.
            conn (MongoClient, optional): MongoDB connection for data retrieval.
                If None, a new connection is established. Default is None.
        
        Returns:
            str: Put option symbol with expiry and strike (e.g., "NIFTY27MAR2526000PE").
        """
        if isinstance(date, datetime):
            dateEpoch = date.timestamp()
        elif isinstance(date, int):
            dateEpoch = float(date)
        elif isinstance(date, float):
            dateEpoch = date
        else:
            raise Exception(
                "date is not a timestamp(float or int) or datetime object")

        if conn is None:
            conn = connectToMongo()

        expiryData = self.fetchAndCacheExpiryData(dateEpoch, baseSym, conn)

        if expiry is None:
            symWithExpiry = baseSym + expiryData["CurrentExpiry"]
        else:
            symWithExpiry = baseSym + expiry

        if strikeDist is None:
            strikeDist = expiryData["StrikeDist"]

        remainder = indexPrice % strikeDist
        atm = (indexPrice - remainder if remainder <= (strikeDist / 2)
               else (indexPrice - remainder + strikeDist))

        putSym = (symWithExpiry + str(int(atm) -
                  (otmFactor * int(strikeDist))) + "PE")

        return putSym

    def fetchAndCacheFnoHistData(self, symbol, timestamp, maxCacheSize=100, conn=None):
        """
        Fetch and cache F&O historical data with automatic cache eviction of expired contracts.
        
        Retrieves 1-minute OHLC data for the specified F&O symbol at the given timestamp.
        Maintains an in-memory cache to avoid redundant database queries. Automatically removes
        expired option contracts from cache when the current timeData exceeds their expiry time.
        
        Parameters:
            symbol (str): F&O symbol to fetch data for (e.g., "NIFTY27MAR2526000CE").
            timestamp (float): Epoch timestamp for the data request.
            maxCacheSize (int, optional): Maximum number of symbols to keep in cache before eviction.
                Default is 100.
            conn (MongoClient, optional): MongoDB connection for data retrieval.
                If None, uses the instance connection. Default is None.
        
        Returns:
            pd.Series: OHLC and other data at the specified timestamp for the symbol.
        """
        # print(len(self.symbolDataCache))
        if len(self.symbolDataCache) > maxCacheSize:
            symbolToDelete = []
            for sym in self.symbolDataCache.keys():
                idx = next(i for i, char in enumerate(
                    sym) if char.isdigit())
                optionExpiry = (datetime.strptime(
                    sym[idx:idx + 7], "%d%b%y").timestamp() + 55800)

                if self.timeData > optionExpiry:
                    symbolToDelete.append(sym)
                    # del self.symbolDataCache[symbol]

            if symbolToDelete:
                for sym in symbolToDelete:
                    del self.symbolDataCache[sym]

        if symbol in self.symbolDataCache.keys():
            return self.symbolDataCache[symbol].loc[timestamp]

        else:
            idx = next(i for i, char in enumerate(symbol) if char.isdigit())
            optionExpiry = (datetime.strptime(
                symbol[idx:idx + 7], "%d%b%y").timestamp() + 55800)

            self.symbolDataCache[symbol] = getFnoBacktestData(
                symbol, timestamp, optionExpiry, "1Min", conn)

            return self.symbolDataCache[symbol].loc[timestamp]

    def fetchAndCacheExpiryData(self, date, sym, conn=None):
        """
        Fetch and cache option expiry metadata (current expiry, strike distance, etc.).
        
        Retrieves expiry-related information for a given base symbol and date from MongoDB FNO_Expiry
        collection. Caches the full expiry dataset indexed by date for efficient subsequent lookups.
        Uses binary search to find the nearest available expiry date for a given timestamp.
        
        Parameters:
            date (datetime or float): Reference date for expiry lookup. Can be datetime object
                or epoch timestamp (float). Time is normalized to 15:30 (market close) for consistency.
            sym (str): Base symbol for which expiry data is requested (e.g., "NIFTY50", "BANKNIFTY").
            conn (MongoClient, optional): MongoDB connection for data retrieval.
                If None, a new connection is established. Default is None.
        
        Returns:
            dict: Dictionary containing expiry metadata including:
                - CurrentExpiry: Nearest available expiry date
                - StrikeDist: Strike price interval for this symbol
                - Other expiry-specific fields from the database
        
        Raises:
            Exception: If date is not a datetime object or float timestamp, or on database errors.
        """
        try:
            if isinstance(date, datetime):
                getDatetime = date
            elif isinstance(date, float):
                getDatetime = datetime.fromtimestamp(date)
            else:
                raise Exception(
                    "date is not a timestamp(float) or datetime object")

            getDatetime = getDatetime.replace(hour=15, minute=30)

            if sym in self.expiryDataCache.keys():
                index = self.expiryDataCache[sym].index.searchsorted(
                    getDatetime) + 1
                if (index < len(self.expiryDataCache[sym]) and self.expiryDataCache[sym].index[index] == getDatetime):
                    expiryDict = self.expiryDataCache[sym].iloc[index].to_dict(
                    )
                elif index > 0:
                    expiryDict = self.expiryDataCache[sym].iloc[index - 1].to_dict()
                return expiryDict

            else:
                if conn is None:
                    conn = connectToMongo()

                db = conn["FNO_Expiry"]
                collection = db["Data"]

                rec = collection.find({"Sym": sym})
                rec = list(rec)

                if rec:
                    df = pd.DataFrame(rec)
                    df["Date"] = pd.to_datetime(df["Date"])
                    df["Date"] = df["Date"] + pd.Timedelta(hours=15,
                                                           minutes=30)
                    df.set_index("Date", inplace=True)
                    df.sort_index(inplace=True, ascending=True)

                    self.expiryDataCache[sym] = df

                    return self.fetchAndCacheExpiryData(date, sym)
        except Exception as e:
            raise Exception(e)


class optIntraDayAlgoLogic(optAlgoLogic):
    """
    Options intraday trading logic with daily CSV snapshot persistence.
    
    Extends optAlgoLogic specifically for intraday options trading strategies.
    Automatically saves open and closed trade snapshots to CSV files with daily filenames,
    enabling easy tracking of trading activity across multiple trading days.
    
    Inherits:
        All attributes and methods from optAlgoLogic.
    """

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None, saveCsv=False):
        """
        Record an options entry order with optional daily CSV persistence.
        
        Calls parent entryOrder method to record the trade, then optionally saves the current
        openPnl DataFrame to a date-stamped CSV file for daily tracking.
        
        Parameters:
            entryPrice (float): Entry price of the option contract.
            symbol (str): Option symbol (e.g., "NIFTY27MAR2526000CE").
            quantity (int): Number of contracts.
            positionStatus (str): Position direction ("BUY" or "SELL").
            extraColDict (dict, optional): Additional custom columns for the trade. Default is None.
            saveCsv (bool, optional): If True, saves openPnl to CSV with current date in filename.
                Default is False.
        
        Returns:
            None
        """
        super().entryOrder(entryPrice, symbol, quantity, positionStatus, extraColDict)
        if saveCsv:
            self.openPnl.to_csv(
                f"{self.fileDir['backtestResultsOpenPnl']}{self.humanTime.date()}_openPnl.csv"
            )

    def exitOrder(self, index, exitType, exitPrice=None):
        """
        Record an options exit order and save updated trade snapshots to daily CSV files.
        
        Calls parent exitOrder method to process the exit, then saves both openPnl and closedPnl
        DataFrames to date-stamped CSV files for daily record keeping.
        
        Parameters:
            index (int): Index of the trade in openPnl to close.
            exitType (str): Classification of the exit action.
            exitPrice (float, optional): Exit price. If None, uses CurrentPrice. Default is None.
        
        Returns:
            None
        """
        super().exitOrder(index, exitType, exitPrice)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.humanTime.date()}_openPnl.csv"
        )
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}{self.humanTime.date()}_closePnl.csv"
        )


class optOverNightAlgoLogic(optAlgoLogic):
    """
    Options overnight trading logic with persistent CSV storage across sessions.
    
    Extends optAlgoLogic specifically for overnight options trading strategies that span
    multiple trading days. Saves trade snapshots to single CSV files (not date-stamped)
    that persist and accumulate across trading sessions.
    
    Inherits:
        All attributes and methods from optAlgoLogic.
    """

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None, saveCsv=False):
        """
        Record an options entry order with optional persistent CSV storage.
        
        Calls parent entryOrder method to record the trade, then optionally saves the current
        openPnl DataFrame to a persistent CSV file (without date stamp) that accumulates across sessions.
        
        Parameters:
            entryPrice (float): Entry price of the option contract.
            symbol (str): Option symbol (e.g., "NIFTY27MAR2526000CE").
            quantity (int): Number of contracts.
            positionStatus (str): Position direction ("BUY" or "SELL").
            extraColDict (dict, optional): Additional custom columns for the trade. Default is None.
            saveCsv (bool, optional): If True, saves openPnl to persistent CSV file.
                Default is False.
        
        Returns:
            None
        """
        super().entryOrder(entryPrice, symbol, quantity, positionStatus, extraColDict)
        if saveCsv:
            self.openPnl.to_csv(
                f"{self.fileDir['backtestResultsOpenPnl']}openPnl.csv")

    def exitOrder(self, index, exitType, exitPrice=None):
        """
        Record an options exit order and update persistent CSV files.
        
        Calls parent exitOrder method to process the exit, then saves both openPnl and closedPnl
        DataFrames to persistent CSV files (without date stamps) that accumulate across sessions.
        
        Parameters:
            index (int): Index of the trade in openPnl to close.
            exitType (str): Classification of the exit action.
            exitPrice (float, optional): Exit price. If None, uses CurrentPrice. Default is None.
        
        Returns:
            None
        """
        super().exitOrder(index, exitType, exitPrice)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}openPnl.csv")
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}closePnl.csv")


class equityOverNightAlgoLogic(baseAlgoLogic):
    """
    Equity overnight trading logic with persistent position tracking.
    
    Extends baseAlgoLogic for equity trading strategies that span multiple days.
    Manages open and closed positions with persistent CSV storage. Unlike intraday strategies,
    uses non-dated filenames to accumulate position history across sessions.
    
    Inherits:
        Core trade management methods from baseAlgoLogic.
    
    Attributes:
        stockName (str): Name of the equity stock being traded.
    """

    def __init__(self, stockName, fileDir):
        """
        Initialize equityOverNightAlgoLogic with stock metadata and result directories.
        
        Sets up trade tracking DataFrames, file directories, and logging specific to overnight
        equity trading. Unlike baseAlgoLogic, does not create subdirectory structure (uses provided fileDir).
        
        Parameters:
            stockName (str): Name of the equity stock being traded.
            fileDir (dict): Dictionary containing pre-configured file paths:
                - backtestResultsOpenPnl: Directory for open position CSVs
                - backtestResultsClosePnl: Directory for closed position CSVs
                - backtestResultsStrategyLogs: Directory for log files
        """
        self.stockName = stockName

        self.timeData = 0
        self.humanTime = datetime.fromtimestamp(0)

        self.unrealizedPnl = 0
        self.realizedPnl = 0
        self.netPnl = 0

        self.openPnl = pd.DataFrame(columns=[
                                    "EntryTime", "Symbol", "EntryPrice", "CurrentPrice", "Quantity", "PositionStatus", "Pnl",])
        self.closedPnl = pd.DataFrame(columns=[
                                      "Key", "ExitTime", "Symbol", "EntryPrice", "ExitPrice", "Quantity", "PositionStatus", "Pnl", "ExitType",])

        self.fileDir = fileDir

        self.strategyLogger = setup_logger(
            "strategyLogger",
            f"{self.fileDir['backtestResultsStrategyLogs']}{self.stockName}_log.log",
        )
        self.strategyLogger.propagate = False

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None, saveCsv=False):
        """
        Record an equity entry order with optional persistent CSV storage.
        
        Calls parent entryOrder method to record the trade, then optionally saves the current
        openPnl DataFrame to a persistent CSV file with stock-name prefix for identification.
        
        Parameters:
            entryPrice (float): Entry price of the equity.
            symbol (str): Stock ticker symbol.
            quantity (int): Number of shares.
            positionStatus (str): Position direction ("BUY" or "SELL").
            extraColDict (dict, optional): Additional custom columns for the trade. Default is None.
            saveCsv (bool, optional): If True, saves openPnl to persistent CSV file.
                Default is False.
        
        Returns:
            None
        """
        super().entryOrder(entryPrice, symbol, quantity, positionStatus, extraColDict)
        if saveCsv:
            self.openPnl.to_csv(
                f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_openPnl.csv"
            )

    def exitOrder(self, index, exitType, exitPrice=None):
        """
        Record an equity exit order and update persistent CSV files.
        
        Calls parent exitOrder method to process the exit, then saves both openPnl and closedPnl
        DataFrames to persistent CSV files with stock-name prefix for identification.
        
        Parameters:
            index (int): Index of the trade in openPnl to close.
            exitType (str): Classification of the exit action.
            exitPrice (float, optional): Exit price. If None, uses CurrentPrice. Default is None.
        
        Returns:
            None
        """
        super().exitOrder(index, exitType, exitPrice)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_openPnl.csv"
        )
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}{self.stockName}_closedPnl.csv"
        )


class equityIntradayAlgoLogic(baseAlgoLogic):
    """
    Equity intraday trading logic with daily position snapshots.
    
    Extends baseAlgoLogic for single-day equity trading strategies.
    Automatically saves open and closed position snapshots to CSV files with daily filenames,
    enabling easy tracking of intraday trading activity. Logger is initialized/updated for each
    new trading day.
    
    Inherits:
        Core trade management methods from baseAlgoLogic.
    
    Attributes:
        stockName (str): Name of the equity stock being traded.
    """

    def __init__(self, stockName, fileDir):
        """
        Initialize equityIntradayAlgoLogic with stock metadata and result directories.
        
        Sets up trade tracking DataFrames, file directories, and logging specific to intraday
        equity trading. Logger is initialized with date in the name and can be refreshed via
        init_logger() when trading session moves to a new day.
        
        Parameters:
            stockName (str): Name of the equity stock being traded.
            fileDir (dict): Dictionary containing pre-configured file paths:
                - backtestResultsOpenPnl: Directory for open position CSVs
                - backtestResultsClosePnl: Directory for closed position CSVs
                - backtestResultsStrategyLogs: Directory for log files
        """
        self.stockName = stockName

        self.timeData = 0
        self.humanTime = datetime.fromtimestamp(0)

        self.unrealizedPnl = 0
        self.realizedPnl = 0
        self.netPnl = 0

        self.openPnl = pd.DataFrame(columns=[
                                    "EntryTime", "Symbol", "EntryPrice", "CurrentPrice", "Quantity", "PositionStatus", "Pnl",])
        self.closedPnl = pd.DataFrame(columns=[
                                      "Key", "ExitTime", "Symbol", "EntryPrice", "ExitPrice", "Quantity", "PositionStatus", "Pnl", "ExitType",])

        self.fileDir = fileDir

        self.strategyLogger = setup_logger(
            f"{self.stockName}_{self.humanTime.date()}_strategyLogger", f"{self.fileDir['backtestResultsStrategyLogs']}{self.stockName}_{self.humanTime.date()}_log.log")
        self.strategyLogger.propagate = False

    def init_logger(self):
        """
        Reinitialize the logger with current date in filename.
        
        Creates a new logger instance for a new trading day. Call this method when humanTime
        changes to a new date to start a fresh log file.
        
        Returns:
            None
        """
        self.strategyLogger = setup_logger(
            f"{self.stockName}_{self.humanTime.date()}_logger", f"{self.fileDir['backtestResultsStrategyLogs']}{self.stockName}_{self.humanTime.date()}_log.log")
        self.strategyLogger.propagate = False

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None, saveCsv=False):
        """
        Record an equity entry order with optional daily CSV persistence.
        
        Calls parent entryOrder method to record the trade, then optionally saves the current
        openPnl DataFrame to a date-stamped CSV file for daily tracking.
        
        Parameters:
            entryPrice (float): Entry price of the equity.
            symbol (str): Stock ticker symbol.
            quantity (int): Number of shares.
            positionStatus (str): Position direction ("BUY" or "SELL").
            extraColDict (dict, optional): Additional custom columns for the trade. Default is None.
            saveCsv (bool, optional): If True, saves openPnl to CSV with current date in filename.
                Default is False.
        
        Returns:
            None
        """
        super().entryOrder(entryPrice, symbol, quantity, positionStatus, extraColDict)
        if saveCsv:
            self.openPnl.to_csv(
                f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_{self.humanTime.date()}_openPnl.csv"
            )

    def exitOrder(self, index, exitType, exitPrice=None):
        """
        Record an equity exit order and save updated trade snapshots to daily CSV files.
        
        Calls parent exitOrder method to process the exit, then saves both openPnl and closedPnl
        DataFrames to date-stamped CSV files for daily record keeping.
        
        Parameters:
            index (int): Index of the trade in openPnl to close.
            exitType (str): Classification of the exit action.
            exitPrice (float, optional): Exit price. If None, uses CurrentPrice. Default is None.
        
        Returns:
            None
        """
        super().exitOrder(index, exitType, exitPrice)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_{self.humanTime.date()}_openPnl.csv"
        )
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}{self.stockName}_{self.humanTime.date()}_closedPnl.csv"
        )
