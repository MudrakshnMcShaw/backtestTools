import numpy as np
import talib as ta
from backtestTools.expiry import getExpiryData
from datetime import datetime, time, timedelta
from backtestTools.algoLogic import optOverNightAlgoLogic
from backtestTools.util import calculateDailyReport, limitCapital, generateReportFile
from backtestTools.histData import getFnoBacktestData

# sys.path.insert(1, '/root/backtestTools')


# Define a class algoLogic that inherits from optOverNightAlgoLogic
class algoLogic(optOverNightAlgoLogic):

    # Define a method to get current expiry epoch
    def getCurrentExpiryEpoch(self, date, baseSym):
        # Fetch expiry data for current and next expiry
        expiryData = getExpiryData(date, baseSym)
        nextExpiryData = getExpiryData(date + 86400, baseSym)

        # Select appropriate expiry based on the current date
        expiry = expiryData["CurrentExpiry"]
        expiryDatetime = datetime.strptime(expiry, "%d%b%y")

        if self.humanTime.date() == expiryDatetime.date():
            expiry = nextExpiryData["CurrentExpiry"]
        else:
            expiry = expiryData["CurrentExpiry"]

        # Set expiry time to 15:20 and convert to epoch
        expiryDatetime = datetime.strptime(expiry, "%d%b%y")
        expiryDatetime = expiryDatetime.replace(hour=15, minute=20)
        expiryEpoch = expiryDatetime.timestamp()

        return expiryEpoch

    # Define a method to execute the algorithm
    def run(self, startDate, endDate, baseSym, indexSym):

        # Add necessary columns to the DataFrame
        col = ["Target", "Stoploss", "BaseSymStoploss", "Expiry"]
        self.addColumnsToOpenPnlDf(col)

        # Convert start and end dates to timestamps
        startEpoch = startDate.timestamp()
        endEpoch = endDate.timestamp()

        try:
            # Fetch historical data for backtesting
            df = getFnoBacktestData(indexSym, startEpoch, endEpoch, "1Min")
            df_5min = getFnoBacktestData(
                indexSym, startEpoch - 432000, endEpoch, "5Min")
        except Exception as e:
            # Log an exception if data retrieval fails
            self.strategyLogger.info(
                f"Data not found for {baseSym} in range {startDate} to {endDate}")
            raise Exception(e)

        # Drop rows with missing values
        df.dropna(inplace=True)
        df_5min.dropna(inplace=True)

        # Calculate RSI indicator
        df_5min["rsi"] = ta.RSI(df_5min["c"], timeperiod=14)
        df_5min.dropna(inplace=True)

        # Filter dataframe from timestamp greater than start time timestamp
        df_5min = df_5min[df_5min.index > startEpoch]

        # Determine crossover signals
        df_5min["rsiCross60"] = np.where(
            (df_5min["rsi"] > 60) & (df_5min["rsi"].shift(1) <= 60), 1, 0)
        df_5min["rsiCross40"] = np.where(
            (df_5min["rsi"] < 40) & (df_5min["rsi"].shift(1) >= 40), 1, 0)
        df_5min["rsiCross50"] = np.where((df_5min["rsi"] >= 50) & (df_5min["rsi"].shift(
            1) < 50), 1, np.where((df_5min["rsi"] <= 50) & (df_5min["rsi"].shift(1) > 50), 1, 0),)

        df.to_csv(
            f"{self.fileDir['backtestResultsCandleData']}{indexName}_1Min.csv")
        df_5min.to_csv(
            f"{self.fileDir['backtestResultsCandleData']}{indexName}_5Min.csv"
        )

        # Strategy Parameters
        callEntryAllow = True
        putEntryAllow = True
        callTradeCounter = 0
        putTradeCounter = 0
        lastIndexTimeData = [0, 0]
        last5MinIndexTimeData = [0, 0]

        # Loop through each timestamp in the DataFrame index
        for timeData in df.index:
            # Reset tradeCounter on new day
            callTradeCounter = (0 if self.humanTime.date() != datetime.fromtimestamp(
                timeData).date() else callTradeCounter)
            putTradeCounter = (0 if self.humanTime.date() != datetime.fromtimestamp(
                timeData).date() else putTradeCounter)

            self.timeData = float(timeData)
            self.humanTime = datetime.fromtimestamp(timeData)
            print(self.humanTime)

            # Skip time periods outside trading hours
            if (self.humanTime.time() < time(9, 16)) | (self.humanTime.time() > time(15, 30)):
                continue

            # Update lastIndexTimeData
            lastIndexTimeData.pop(0)
            lastIndexTimeData.append(timeData - 60)
            last5MinIndexTimeData.pop(0)
            last5MinIndexTimeData.append(timeData - 300)

            # Strategy Specific Trading Time
            if (self.humanTime.time() < time(9, 20)) | (self.humanTime.time() > time(15, 25)):
                continue

            # Log relevant information
            if lastIndexTimeData[1] in df.index:
                self.strategyLogger.info(
                    f"Datetime: {self.humanTime}\tClose: {df.at[lastIndexTimeData[1],'c']}")

            # Update current price for open positions
            if not self.openPnl.empty:
                for index, row in self.openPnl.iterrows():
                    try:
                        data = self.fetchAndCacheFnoHistData(
                            row["Symbol"], lastIndexTimeData[1])
                        self.openPnl.at[index, "CurrentPrice"] = data["c"]
                    except Exception as e:
                        self.strategyLogger.info(e)

            # Calculate and update PnL
            self.pnlCalculator()

            # Check for exit conditions and execute exit orders
            if not self.openPnl.empty:
                for index, row in self.openPnl.iterrows():

                    symSide = row["Symbol"]
                    symSide = symSide[len(symSide) - 2:]

                    if row["CurrentPrice"] <= row["Target"]:
                        exitType = "Target Hit"
                        self.exitOrder(index, exitType, row["Target"])
                    elif row["CurrentPrice"] >= row["Stoploss"]:
                        exitType = "Stoploss Hit"
                        self.exitOrder(index, exitType, row["Stoploss"])
                    elif self.timeData >= row["Expiry"]:
                        exitType = "Time Up"
                        self.exitOrder(index, exitType)
                    elif last5MinIndexTimeData[1] in df_5min.index:
                        if (df_5min.at[last5MinIndexTimeData[1], "c"] >= row["BaseSymStoploss"]) & (symSide == "CE"):
                            exitType = "Underlying Asset Candle Stoploss Hit"
                            self.exitOrder(index, exitType)
                        elif (df_5min.at[last5MinIndexTimeData[1], "c"] <= row["BaseSymStoploss"]) & (symSide == "PE"):
                            exitType = "Underlying Asset Candle Stoploss Hit"
                            self.exitOrder(index, exitType)

                    if (index not in self.openPnl.index) & (symSide == "CE"):
                        callTradeCounter += 1
                    elif (index not in self.openPnl.index) & (symSide == "PE"):
                        putTradeCounter += 1

            # Check for entry signals and execute orders
            if last5MinIndexTimeData[1] in df_5min.index:
                if df_5min.at[last5MinIndexTimeData[1], "rsiCross50"] == 1:
                    callEntryAllow = True
                    putEntryAllow = True

                if (callTradeCounter < 3) & (callEntryAllow):
                    if df_5min.at[last5MinIndexTimeData[1], "rsiCross40"] == 1:
                        callSym = self.getCallSym(
                            self.timeData, baseSym, df.at[last5MinIndexTimeData[1], "c"])
                        expiryEpoch = self.getCurrentExpiryEpoch(
                            self.timeData, baseSym)
                        lotSize = int(getExpiryData(
                            self.timeData, baseSym)["LotSize"])

                        try:
                            data = self.fetchAndCacheFnoHistData(
                                callSym, last5MinIndexTimeData[1])
                        except Exception as e:
                            self.strategyLogger.info(e)

                        target = 0.5 * data["c"]
                        stoploss = 1.3 * data["c"]
                        baseSymStoploss = max(
                            [df_5min.at[last5MinIndexTimeData[1], "h"], df_5min.at[timeData, "h"],])

                        self.entryOrder(data["c"], callSym, lotSize, "SELL", {
                                        "Target": target,
                                        "Stoploss": stoploss,
                                        "BaseSymStoploss": baseSymStoploss,
                                        "Expiry": expiryEpoch, }
                                        )
                        callEntryAllow = False

                if (putTradeCounter < 3) & (putEntryAllow):
                    if df_5min.at[last5MinIndexTimeData[1], "rsiCross60"] == 1:
                        putSym = self.getPutSym(
                            self.timeData, baseSym, df.at[last5MinIndexTimeData[1], "c"])
                        expiryEpoch = self.getCurrentExpiryEpoch(
                            self.timeData, baseSym)
                        lotSize = int(getExpiryData(
                            self.timeData, baseSym)["LotSize"])

                        try:
                            data = self.fetchAndCacheFnoHistData(
                                putSym, last5MinIndexTimeData[1])
                        except Exception as e:
                            self.strategyLogger.info(e)

                        target = 0.5 * data["c"]
                        stoploss = 1.3 * data["c"]
                        baseSymStoploss = min(
                            [df_5min.at[last5MinIndexTimeData[1], "l"], df_5min.at[timeData, "l"],])

                        self.entryOrder(data["c"], putSym, lotSize, "SELL", {
                                        "Target": target,
                                        "Stoploss": stoploss,
                                        "BaseSymStoploss": baseSymStoploss,
                                        "Expiry": expiryEpoch, },
                                        )
                        putEntryAllow = False

        # Calculate final PnL and combine CSVs
        self.pnlCalculator()
        self.combinePnlCsv()

        return self.closedPnl, self.fileDir["backtestResultsStrategyUid"]


if __name__ == "__main__":
    startTime = datetime.now()

    # Define Strategy Nomenclature
    devName = "NA"
    strategyName = "rdx"
    version = "v1"

    # Define Start date and End date
    startDate = datetime(2023, 1, 1, 9, 15)
    endDate = datetime(2023, 1, 31, 15, 30)

    # Create algoLogic object
    algo = algoLogic(devName, strategyName, version)

    # Define Index Name
    baseSym = "NIFTY"
    indexName = "NIFTY 50"

    # Execute the algorithm
    closedPnl, fileDir = algo.run(startDate, endDate, baseSym, indexName)

    print("Calculating Daily Pnl")
    dr = calculateDailyReport(
        closedPnl, fileDir, timeFrame=timedelta(minutes=5), mtm=True
    )

    limitCapital(closedPnl, fileDir, maxCapitalAmount=1000)

    generateReportFile(dr, fileDir)

    endTime = datetime.now()
    print(f"Done. Ended in {endTime-startTime}")

    # Backtest time = 09:50
    # Backtest time = 07:27
    # Backtest time = 07:27
