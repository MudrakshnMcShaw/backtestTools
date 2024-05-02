import os
import pandas as pd
from datetime import datetime
from backtestTools.histData import connectToMongo, getFnoBacktestData
from backtestTools.util import setup_logger
from backtestTools.expiry import getExpiryData


class baseAlgoLogic:
    """
    The `baseAlgoLogic` class is a foundational class for implementing algorithmic trading logic.
    It provides methods for managing trades, calculating profit and loss (PnL), and handling data storage.
    This class serves as a base for more specific algorithmic trading strategies.

        Attributes:
            conn (MongoClient): Stores a MongoDB connection object. Initially set to None.

            timeData (float): Stores timestamp

            humanTime (datetime): Stores python datetime object

            unrealisedPnl (int): Stores Unrealized Profit and Loss

            realisedPnl (int): Stores Realized Profit and Loss

            netPnl (int): Stores Net Profit and Loss

            openPnl (DataFrame): Dataframe that stores open trades

            closedPnl (DataFrame): Dataframe that stores closed trades

            fileDir (Dictionary): Dictionary containing several file directories for storing files

            > backtestResultsStrategyUid - Backtest Results Folder

            > backtestResultsOpenPnl: File directory to store openPnl csv

            > backtestResultsClosePnl: File directory to store closedPnl csv

            > backtestResultsCandleData: File directory to store OHLC Data csv

            > backtestResultsStrategyLogs: File directory to store strategy logs

            strategyLogger (logging): Logger to log relevant info

    """

    def __init__(self, devName, strategyName, version):
        """
        This method initializes an instance of the `baseAlgoLogic` class.

            Parameters:
                devName (string): Developer Name
                strategyName (string): Strategy Name
                version (string): Version Name

        """

        self.devName = devName
        self.strategyName = strategyName
        self.version = version

        self.conn = None
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
        Creates multiple new column in openPnl Dataframe

        Parameters:
            columns (list): List of column names(string) to be added.
        """

        for col in columns:
            self.openPnl[col] = None

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None):
        """
        Executes an entry order for a trade and adds it to the `openPnl` DataFrame.

        Parameters:
            entryPrice (float): List of column names(string) to be added.

            symbol (string): Symbol of the asset being traded.

            quantity (int): Quantity of the asset being traded.

            positionStatus (string): Position status, either "BUY" or "SELL".

            extraColDict (Dictionary, optional): Additional columns to be included in the trade entry.
        """

        newTradeDict = {
            "EntryTime": self.humanTime,
            "Symbol": symbol,
            "EntryPrice": entryPrice,
            "CurrentPrice": entryPrice,
            "Quantity": quantity,
            "PositionStatus": 1 if positionStatus == "BUY" else -1,
        }
        if extraColDict:
            for keys in extraColDict:
                newTradeDict[keys] = extraColDict[keys]
        newTrade = pd.DataFrame(newTradeDict, index=[0])

        self.openPnl = pd.concat([self.openPnl, newTrade], ignore_index=True)
        self.openPnl.reset_index(inplace=True, drop=True)
        # self.openPnl.reset_index(inplace=True)

        # logging.info(
        #     f"Datetime: {self.humanTime}\t Entry Order of {symbol} executed at {entryPrice}")
        self.strategyLogger.info(
            f"Datetime: {self.humanTime}\t Entry Order of {symbol} executed at {entryPrice}"
        )

    def exitOrder(self, index, exitType, exitPrice=None):
        """
        Executes an exit order for a trade and moves it from the `openPnl` DataFrame to the `closedPnl` DataFrame.

        Parameters:
            index (int): Index of the trade in the `openPnl` DataFrame.

            exitType (string): Type of exit order.

            exitPrice (float, optional): Exit price of the trade.
        """
        # Get the trade details from openPnl
        trade_to_close = self.openPnl.loc[index].to_dict()

        # Remove the trade from openPnl DataFrame
        self.openPnl.drop(index=index, inplace=True)

        # Create a new row for closedPnl DataFrame
        trade_to_close["Key"] = trade_to_close["EntryTime"]
        trade_to_close["ExitTime"] = self.humanTime
        trade_to_close["ExitPrice"] = (
            trade_to_close["CurrentPrice"] if not exitPrice else exitPrice)
        trade_to_close["Pnl"] = ((trade_to_close["ExitPrice"] - trade_to_close["EntryPrice"])
                                 * trade_to_close["Quantity"] * trade_to_close["PositionStatus"])
        trade_to_close["ExitType"] = exitType

        for col in self.openPnl.columns:
            if col not in self.closedPnl.columns:
                del trade_to_close[col]

        # Append the closed trade to closedPnl DataFrame
        self.closedPnl = pd.concat(
            [self.closedPnl, pd.DataFrame([trade_to_close])], ignore_index=True)
        self.closedPnl.reset_index(inplace=True, drop=True)

        # logging.info(
        #     f"Datetime: {self.humanTime}\t Exit Order of {trade_to_close['Symbol']} executed at {trade_to_close['ExitPrice']}")
        self.strategyLogger.info(
            f"Datetime: {self.humanTime}\t Exit Order of {trade_to_close['Symbol']} executed at {trade_to_close['ExitPrice']}"
        )

    def pnlCalculator(self):
        """
        Calculates the profit and loss (PnL) for both open and closed trades.
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
            self.closedPnl.sort_values(by=["Key"], inplace=True)
            self.closedPnl["Pnl"] = ((self.closedPnl["ExitPrice"] - self.closedPnl["EntryPrice"])
                                     * self.closedPnl["Quantity"] * self.closedPnl["PositionStatus"])
            self.realizedPnl = self.closedPnl["Pnl"].sum()
        else:
            self.realizedPnl = 0

        # Calculate net PnL by adding realized and unrealized PnLs
        self.netPnl = self.unrealizedPnl + self.realizedPnl

    def combinePnlCsv(self):
        """
        Combines and saves the data of open and closed trades to CSV files.

        Return:
            openPnl (DataFrame): Combined DataFrame of open trades.

            closedPnl (DataFrame): Combined DataFrame of closed trades.
        """
        openPnl = pd.DataFrame(columns=[
                               "EntryTime", "Symbol", "EntryPrice", "CurrentPrice", "Quantity", "PositionStatus", "Pnl",])
        closedPnl = pd.DataFrame(columns=["Key", "ExitTime", "Symbol", "EntryPrice",
                                 "ExitPrice", "Quantity", "PositionStatus", "Pnl", "ExitType",])

        openCsvFiles = []
        for file in os.listdir(os.path.join(os.getcwd(), self.fileDir["backtestResultsOpenPnl"])):
            if file.endswith(".csv"):
                openCsvFiles.append(os.path.join(os.getcwd(), os.path.join(
                    self.fileDir["backtestResultsOpenPnl"], file),))

        for csvFile in openCsvFiles:
            openPnl = pd.concat([openPnl, pd.read_csv(csvFile)])

        closeCsvFiles = []
        for file in os.listdir(os.path.join(os.getcwd(), self.fileDir["backtestResultsClosePnl"])):
            if file.endswith(".csv"):
                closeCsvFiles.append(os.path.join(os.getcwd(), os.path.join(
                    self.fileDir["backtestResultsClosePnl"], file),))

        for csvFile in closeCsvFiles:
            closedPnl = pd.concat([closedPnl, pd.read_csv(csvFile)])

        openPnl["EntryTime"] = pd.to_datetime(openPnl["EntryTime"])
        if "Unnamed: 0" in openPnl.columns:
            openPnl.drop(columns=["Unnamed: 0"], inplace=True)
        openPnl.sort_values(by=["EntryTime"], inplace=True)
        openPnl.reset_index(inplace=True, drop=True)

        closedPnl["Key"] = pd.to_datetime(closedPnl["Key"])
        closedPnl["ExitTime"] = pd.to_datetime(closedPnl["ExitTime"])
        if "Unnamed: 0" in closedPnl.columns:
            closedPnl.drop(columns=["Unnamed: 0"], inplace=True)
        closedPnl.sort_values(by=["Key"], inplace=True)
        closedPnl.reset_index(inplace=True, drop=True)

        openPnl.to_csv(
            f"{self.fileDir['backtestResultsStrategyUid']}openPnl_{self.devName}_{self.strategyName}_{self.version}_{self.fileDirUid}.csv", index=False,)
        # logging.info("OpenPNL.csv saved.")
        self.strategyLogger.info("OpenPNL.csv saved.")

        closedPnl.to_csv(
            f"{self.fileDir['backtestResultsStrategyUid']}closePnl_{self.devName}_{self.strategyName}_{self.version}_{self.fileDirUid}.csv", index=False,)
        # logging.info("ClosePNL.csv saved.")
        self.strategyLogger.info("ClosePNL.csv saved.")

        # return openPnl, closedPnl
        return closedPnl


class optAlgoLogic(baseAlgoLogic):
    """
    Options Algo Logic Class
    Inherits from baseAlgoLogic class.

    Attributes:
        Inherits all attributes and functions from the baseAlgoLogic class.
    """

    def __init__(self, devName, strategyName, version):
        super().__init__(devName, strategyName, version)
        self.symbolDataCache = {}
        self.expiryDataCache = {}

    def getCallSym(self, date, baseSym, indexPrice, otmFactor=0):
        """
        Creates the call symbol based on provided parameters.

        Parameters:
            date (datetime or float): Date at which the expiry date needs to be decided.

            baseSym (string): Base symbol for the option.

            indexPrice (float): Current price of the baseSym.

            otmFactor (int, optional): Factor for calculating the strike price. Default is 0.

        Returns:
            callSym (string): Call symbol generated based on the parameters.
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

        expiryData = getExpiryData(dateEpoch, baseSym)
        nextExpiryData = getExpiryData(dateEpoch + 86400, baseSym)

        if expiryData["CurrentExpiry"] == nextExpiryData["CurrentExpiry"]:
            symWithExpiry = baseSym + expiryData["CurrentExpiry"]
        else:
            symWithExpiry = baseSym + nextExpiryData["CurrentExpiry"]

        remainder = indexPrice % expiryData["StrikeDist"]
        atm = (indexPrice - remainder if remainder <= (expiryData["StrikeDist"] / 2) else (
            indexPrice - remainder + expiryData["StrikeDist"]))

        callSym = (symWithExpiry + str(int(atm) +
                   (otmFactor * int(expiryData["StrikeDist"]))) + "CE")

        return callSym

    def getPutSym(self, date, baseSym, indexPrice, otmFactor=0):
        """
        Creates the put symbol based on provided parameters.

        Parameters:
            date (datetime or float): Date at which the expiry date needs to be decided.

            baseSym (string): Base symbol for the option.

            indexPrice (float): Current price of the baseSym.

            otmFactor (int, optional): Factor for calculating the strike price. Default is 0.

        Returns:
            putSym (string): Put symbol generated based on the parameters.
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

        expiryData = getExpiryData(dateEpoch, baseSym)
        nextExpiryData = getExpiryData(dateEpoch + 86400, baseSym)

        expiry = expiryData["CurrentExpiry"]
        expiryDatetime = datetime.strptime(expiry, "%d%b%y")

        if self.humanTime.date() == expiryDatetime.date():
            symWithExpiry = baseSym + nextExpiryData["CurrentExpiry"]
        else:
            symWithExpiry = baseSym + expiryData["CurrentExpiry"]

        remainder = indexPrice % expiryData["StrikeDist"]
        atm = (indexPrice - remainder if remainder <= (expiryData["StrikeDist"] / 2) else (
            indexPrice - remainder + expiryData["StrikeDist"]))

        putSym = (symWithExpiry + str(int(atm) -
                  (otmFactor * int(expiryData["StrikeDist"]))) + "PE")

        return putSym

    def fetchAndCacheFnoHistData(self, symbol, timestamp, maxCacheSize=50):
        """
        Fetches and caches historical data for a given F&O symbol and timestamp.

        Parameters:
            symbol (str): The F&O symbol for which data needs to be fetched.

            timestamp (float): The timestamp for the data request.

            maxCacheSize (int, optional): Maximum size of the cache. Default is 50.

        Returns:
            DataFrame: Historical data for the specified F&O symbol and timestamp.

        """
        if len(self.symbolDataCache) > maxCacheSize:
            symbolToDelete = []
            for symbol in self.symbolDataCache.keys():
                idx = next(i for i, char in enumerate(
                    symbol) if char.isdigit())
                optionExpiry = (datetime.strptime(
                    symbol[idx:idx + 7], "%d%b%y").timestamp() + 55800)

                if self.timeData > optionExpiry:
                    symbolToDelete.append(symbol)
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
                symbol, timestamp, optionExpiry, "1Min")

            return self.symbolDataCache[symbol].loc[timestamp]

    def fetchAndCacheExpiryData(self, date, sym):
        """
        Fetches and caches expiry data for a given date and symbol from MongoDB collections.
        The fetched data is cached in the `expiryDataCache` attribute of the class instance.

        Parameters:
            date (datetime or float): The date for which expiry data is requested.
                It can be either a datetime object or a timestamp in float format.

            sym (string): The base symbol for which expiry data is requested.

        Returns:
            dictionary: A dictionary containing expiry data if found, otherwise None.
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
    Options Intraday Algo Logic Class
    Inherits from optAlgoLogic class.

    Attributes:
        Inherits all attributes and functions from the optAlgoLogic class.
    """

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None):
        super().entryOrder(entryPrice, symbol, quantity, positionStatus, extraColDict)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.humanTime.date()}_openPnl.csv"
        )

    def exitOrder(self, index, exitType, exitPrice=None):
        super().exitOrder(index, exitType, exitPrice)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.humanTime.date()}_openPnl.csv"
        )
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}{self.humanTime.date()}_closePnl.csv"
        )

    def pnlCalculator(self):
        super().pnlCalculator()
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.humanTime.date()}_openPnl.csv"
        )
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}{self.humanTime.date()}_closePnl.csv"
        )


class optOverNightAlgoLogic(optAlgoLogic):
    """
    Options Overnight Algo Logic Class
    Inherits from optAlgoLogic class.

    Attributes:
        Inherits all attributes and functions from the optAlgoLogic class.
    """

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None):
        super().entryOrder(entryPrice, symbol, quantity, positionStatus, extraColDict)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}openPnl.csv")

    def exitOrder(self, index, exitType, exitPrice=None):
        super().exitOrder(index, exitType, exitPrice)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}openPnl.csv")
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}closePnl.csv")

    def pnlCalculator(self):
        super().pnlCalculator()
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}openPnl.csv")
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}closePnl.csv")


class equityOverNightAlgoLogic(baseAlgoLogic):
    """
    Equity Overnight Algo Logic Class
    Inherits from baseAlgoLogic class.

    Attributes:
        Inherits all attributes and functions from the baseAlgoLogic class.
    """

    def __init__(self, stockName, fileDir):
        """
        Initializes an instance of the `equityOverNightAlgoLogic` class.

        Parameters:
            stockName (string): Name of the stock for which the algorithm is designed.

            fileDir (Dictionary): Dictionary containing file directories for storing files.
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

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None):
        super().entryOrder(entryPrice, symbol, quantity, positionStatus, extraColDict)

        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_openPnl.csv"
        )

    def exitOrder(self, index, exitType, exitPrice=None):
        super().exitOrder(index, exitType, exitPrice)

        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_openPnl.csv"
        )
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}{self.stockName}_closedPnl.csv"
        )

    def pnlCalculator(self):
        super().pnlCalculator()

        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_openPnl.csv"
        )
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}{self.stockName}_closedPnl.csv"
        )


class equityIntradayAlgoLogic(baseAlgoLogic):
    """
    Equity Intraday Algo Logic Class
    Inherits from baseAlgoLogic class.

    Attributes:
        Inherits all attributes and functions from the baseAlgoLogic class.
    """

    def __init__(self, stockName, fileDir):
        """
        Initializes an instance of the `equityIntradayAlgoLogic` class.

        Parameters:
            stockName (string): Name of the stock for which the algorithm is designed.

            fileDir (Dictionary): Dictionary containing file directories for storing files.
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
            "strategyLogger", f"{self.fileDir['backtestResultsStrategyLogs']}/backTest.log",)
        self.strategyLogger.propagate = False

    def init_logger(self):
        self.strategyLogger = setup_logger(f"{self.stockName}_{self.humanTime.date()}_logger",
                                           f"{self.fileDir['backtestResultsStrategyLogs']}{self.stockName}_{self.humanTime.date()}_log.log")
        self.strategyLogger.propagate = False

    def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None):
        super().entryOrder(entryPrice, symbol, quantity, positionStatus, extraColDict)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_{self.humanTime.date()}_openPnl.csv"
        )

    def exitOrder(self, index, exitType, exitPrice=None):
        super().exitOrder(index, exitType, exitPrice)
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_{self.humanTime.date()}_openPnl.csv"
        )
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}{self.stockName}_{self.humanTime.date()}_closedPnl.csv"
        )

    def pnlCalculator(self):
        super().pnlCalculator()
        self.openPnl.to_csv(
            f"{self.fileDir['backtestResultsOpenPnl']}{self.stockName}_{self.humanTime.date()}_openPnl.csv"
        )
        self.closedPnl.to_csv(
            f"{self.fileDir['backtestResultsClosePnl']}{self.stockName}_{self.humanTime.date()}_closedPnl.csv"
        )
