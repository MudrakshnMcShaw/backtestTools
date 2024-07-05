import talib
import logging
import numpy as np
import multiprocessing
from termcolor import colored, cprint
from datetime import datetime, time
from backtestTools.util import setup_logger
from backtestTools.histData import getEquityHistData
from backtestTools.histData import getEquityBacktestData
from backtestTools.algoLogic import baseAlgoLogic, equityOverNightAlgoLogic


class rsiDmiOvernightStrategy(baseAlgoLogic):
    def runBacktest(self, portfolio, startDate, endDate):
        if self.strategyName != "rsiDmiOvernight":
            raise Exception("Strategy Name Mismatch")

        # Calculate total number of backtests
        total_backtests = sum(len(batch) for batch in portfolio)
        completed_backtests = 0
        cprint(
            f"Backtesting: {self.strategyName} UID: {self.fileDirUid}", "green")
        print(colored("Backtesting 0% complete.", "light_yellow"), end="\r")

        for batch in portfolio:
            processes = []
            for stock in batch:
                p = multiprocessing.Process(
                    target=self.backtest, args=(stock, startDate, endDate))
                p.start()
                processes.append(p)

            # Wait for all processes to finish
            for p in processes:
                p.join()
                completed_backtests += 1
                percent_done = (completed_backtests / total_backtests) * 100
                print(colored(f"Backtesting {percent_done:.2f}% complete.", "light_yellow"), end=(
                    "\r" if percent_done != 100 else "\n"))

        return self.fileDir["backtestResultsStrategyUid"], self.combinePnlCsv()

    def backtest(self, stockName, startDate, endDate):

        # Set start and end timestamps for data retrieval
        startTimeEpoch = startDate.timestamp()
        endTimeEpoch = endDate.timestamp()

        stockAlgoLogic = equityOverNightAlgoLogic(stockName, self.fileDir)

        logger = setup_logger(
            stockName, f"{self.fileDir['backtestResultsStrategyLogs']}/{stockName}.log",)
        logger.propagate = False

        try:
            # Subtracting 2592000 to subtract 90 days from startTimeEpoch
            df = getEquityBacktestData(
                stockName, startTimeEpoch-7776000, endTimeEpoch, "D")
        except Exception as e:
            raise Exception(e)

        df.dropna(inplace=True)
        df.index = df.index + 33300

        df["plus_di"] = talib.PLUS_DI(df["h"], df["l"], df["c"], timeperiod=25)
        df["rsi"] = talib.RSI(df["c"], timeperiod=14)

        df["diCross"] = np.where((df["plus_di"] >= 30) & (
            df["plus_di"].shift(1) < 30), 1, 0)
        df["rsiCross"] = np.where((df["rsi"] >= 70) & (df["rsi"].shift(
            1) < 70), 1, np.where((df["rsi"] <= 70) & (df["rsi"].shift(1) > 70), -1, 0))

        # Filter dataframe from timestamp greater than start time timestamp
        df = df[df.index > startTimeEpoch]

        df.to_csv(
            f"{self.fileDir['backtestResultsCandleData']}{stockName}_df.csv")

        amountPerTrade = 100000
        lastIndexTimeData = None

        for timeData in df.index:
            stockAlgoLogic.timeData = timeData
            stockAlgoLogic.humanTime = datetime.fromtimestamp(timeData)

            if lastIndexTimeData in df.index:
                logger.info(
                    f"Datetime: {stockAlgoLogic.humanTime}\tStock: {stockName}\tClose: {df.at[lastIndexTimeData,'c']}")

            if not stockAlgoLogic.openPnl.empty:
                for index, row in stockAlgoLogic.openPnl.iterrows():
                    try:
                        data = getEquityHistData(
                            row['Symbol'], timeData)
                        stockAlgoLogic.openPnl.at[index,
                                                  'CurrentPrice'] = data['o']
                    except Exception as e:
                        logging.info(e)

            stockAlgoLogic.pnlCalculator()

            for index, row in stockAlgoLogic.openPnl.iterrows():
                if lastIndexTimeData in df.index:
                    if df.at[lastIndexTimeData, "l"] <= (0.99*row["EntryPrice"]):
                        exitType = "Stoploss Hit"
                        stockAlgoLogic.exitOrder(
                            index, exitType, (0.99*row["EntryPrice"]))
                    elif (df.at[lastIndexTimeData, "rsiCross"] == -1):
                        exitType = "RSI Exit Signal"
                        stockAlgoLogic.exitOrder(index, exitType)

            if (lastIndexTimeData in df.index) & (stockAlgoLogic.openPnl.empty):
                if (df.at[lastIndexTimeData, "plus_di"] >= 30) & (df.at[lastIndexTimeData, "rsiCross"] == 1):
                    entry_price = df.at[lastIndexTimeData, "c"]
                    stockAlgoLogic.entryOrder(entry_price, stockName,
                                              (amountPerTrade//entry_price), "BUY")
                elif (df.at[lastIndexTimeData, "rsi"] >= 70) & (df.at[lastIndexTimeData, "diCross"] == 1):
                    entry_price = df.at[lastIndexTimeData, "c"]
                    stockAlgoLogic.entryOrder(entry_price, stockName,
                                              (amountPerTrade//entry_price), "BUY")

            lastIndexTimeData = timeData
            stockAlgoLogic.pnlCalculator()

        if not stockAlgoLogic.openPnl.empty:
            for index, row in stockAlgoLogic.openPnl.iterrows():
                exitType = "Time Up"
                stockAlgoLogic.exitOrder(index, exitType)
        stockAlgoLogic.pnlCalculator()
