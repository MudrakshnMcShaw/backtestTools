import pandas as pd
import talib
import logging
import numpy as np
import multiprocessing
from termcolor import colored, cprint
from datetime import datetime, time, timedelta
from backtestTools.util import setup_logger
# from backtestTools.histData import getEquityHistData
from backtestTools.histData import getEquityBacktestData
from backtestTools.algoLogic import baseAlgoLogic, equityIntradayAlgoLogic


class rsiDmiIntradayStrategy(baseAlgoLogic):
    def runBacktest(self, portfolio, startDate, endDate):
        if self.strategyName != "rsiDmiIntraday":
            raise Exception("Strategy Name Mismatch")

        cprint(
            f"Backtesting: {self.strategyName} UID: {self.fileDirUid}", "green")
        total_days = (endDate.date() - startDate.date()).days
        current_day = -1

        currentDate = startDate.date()
        while currentDate <= endDate.date():
            startTime = datetime.combine(currentDate, time(9, 15, 0))
            endTime = datetime.combine(currentDate, time(15, 30, 0))

            for batch in portfolio:
                processes = []
                for stock in batch:
                    p = multiprocessing.Process(
                        target=self.backtest, args=(stock, startTime, endTime))
                    p.start()
                    processes.append(p)

                # Wait for all processes to finish
                for p in processes:
                    p.join()

            currentDate += timedelta(days=1)
            current_day += 1

            progress_percent = (current_day / total_days) * 100
            print(colored(f"Progress: {current_day}/{total_days} days ({progress_percent:.2f}%)", "light_yellow"),
                  end=("\r" if progress_percent != 100 else "\n"))

        return self.fileDir["backtestResultsStrategyUid"], self.combinePnlCsv()

    def backtest(self, stockName, startDate, endDate):

        # Set start and end timestamps for data retrieval
        startTimeEpoch = startDate.timestamp()
        endTimeEpoch = endDate.timestamp()

        stockAlgoLogic = equityIntradayAlgoLogic(stockName, self.fileDir)
        stockAlgoLogic.humanTime = startDate

        logger = setup_logger(
            stockName, f"{stockAlgoLogic.fileDir['backtestResultsStrategyLogs']}{stockName}_{stockAlgoLogic.humanTime.date()}_log.log",)
        logger.propagate = False

        try:
            # Subtracting 2592000 to subtract 10 days from startTimeEpoch
            df = getEquityBacktestData(
                stockName, startTimeEpoch-864000, endTimeEpoch, "15Min")
        except Exception as e:
            raise Exception(e)

        df.dropna(inplace=True)

        df["plus_di"] = talib.PLUS_DI(df["h"], df["l"], df["c"], timeperiod=25)
        df["minus_di"] = talib.MINUS_DI(
            df["h"], df["l"], df["c"], timeperiod=25)

        df["rsi"] = talib.RSI(df["c"], timeperiod=14)

        df["diPlusCross"] = np.where((df["plus_di"] >= 25) & (
            df["plus_di"].shift(1) < 25), 1, 0)
        df["diMinusCross"] = np.where((df["minus_di"] >= 25) & (
            df["minus_di"].shift(1) < 25), 1, 0)

        df["rsiLongCross"] = np.where((df["rsi"] >= 65) & (df["rsi"].shift(
            1) < 65), 1, np.where((df["rsi"] <= 65) & (df["rsi"].shift(1) > 65), -1, 0))
        df["rsiShortCross"] = np.where((df["rsi"] <= 35) & (df["rsi"].shift(
            1) > 35), 1, np.where((df["rsi"] >= 35) & (df["rsi"].shift(1) < 35), -1, 0))

        # Filter dataframe from timestamp greater than start time timestamp
        df = df[df.index >= startTimeEpoch]
        if df.empty:
            return

        df.to_csv(
            f"{stockAlgoLogic.fileDir['backtestResultsCandleData']}{stockName}_{stockAlgoLogic.humanTime.date()}_df.csv")

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
                    stockAlgoLogic.openPnl.at[index,
                                              "CurrentPrice"] = df.at[lastIndexTimeData, "c"]

            stockAlgoLogic.pnlCalculator()

            for index, row in stockAlgoLogic.openPnl.iterrows():
                if stockAlgoLogic.humanTime.time() >= time(15, 15):
                    exitType = "Time Up"
                    stockAlgoLogic.exitOrder(index, exitType)
                elif row["PositionStatus"] == 1:
                    if row["CurrentPrice"] <= (0.997*row["EntryPrice"]):
                        exitType = "Stoploss Hit"
                        stockAlgoLogic.exitOrder(
                            index, exitType, (0.997*row["EntryPrice"]))
                    elif (df.at[lastIndexTimeData, "rsiLongCross"] == -1):
                        exitType = "RSI Long Exit Signal"
                        stockAlgoLogic.exitOrder(index, exitType)
                elif row["PositionStatus"] == -1:
                    if row["CurrentPrice"] >= (1.003*row["EntryPrice"]):
                        exitType = "Stoploss Hit"
                        stockAlgoLogic.exitOrder(
                            index, exitType, (1.003*row["EntryPrice"]))
                    elif (df.at[lastIndexTimeData, "rsiShortCross"] == -1):
                        exitType = "RSI Short Exit Signal"
                        stockAlgoLogic.exitOrder(index, exitType)

            if (lastIndexTimeData in df.index) & (stockAlgoLogic.humanTime.time() < time(15, 15)):
                if (df.at[lastIndexTimeData, "plus_di"] >= 25) & (df.at[lastIndexTimeData, "rsiLongCross"] == 1):
                    entry_price = df.at[lastIndexTimeData, "c"]
                    stockAlgoLogic.entryOrder(
                        entry_price, stockName,  (amountPerTrade//entry_price), "BUY")
                elif (df.at[lastIndexTimeData, "rsi"] >= 65) & (df.at[lastIndexTimeData, "diPlusCross"] == 1):
                    entry_price = df.at[lastIndexTimeData, "c"]
                    stockAlgoLogic.entryOrder(
                        entry_price, stockName, (amountPerTrade//entry_price), "BUY")
                elif (df.at[lastIndexTimeData, "minus_di"] >= 25) & (df.at[lastIndexTimeData, "rsiShortCross"] == 1):
                    entry_price = df.at[lastIndexTimeData, "c"]
                    stockAlgoLogic.entryOrder(entry_price, stockName,
                                              (amountPerTrade//entry_price), "SELL")
                elif (df.at[lastIndexTimeData, "rsi"] <= 35) & (df.at[lastIndexTimeData, "diMinusCross"] == 1):
                    entry_price = df.at[lastIndexTimeData, "c"]
                    stockAlgoLogic.entryOrder(entry_price, stockName,
                                              (amountPerTrade//entry_price), "SELL")

            lastIndexTimeData = timeData
            stockAlgoLogic.pnlCalculator()
