import threading
import pandas as pd
import talib
import logging
import numpy as np
import multiprocessing
from termcolor import colored, cprint
from datetime import datetime, time, timedelta
from backtestTools.util import setup_logger
from backtestTools.histData import getEquityHistData
from backtestTools.histData import getEquityBacktestData
from backtestTools.algoLogic import baseAlgoLogic, equityIntradayAlgoLogic


rsi_upperBand = 60
rsi_lowerBand = 40
di_cross = 15


class rsiDmiIntradayStrategy(baseAlgoLogic):
    def runBacktest(self, portfolio, startDate, endDate):
        if self.strategyName != "rsiDmiIntraday":
            raise Exception("Strategy Name Mismatch")

        # Calculate total number of backtests
        total_backtests = sum(len(batch) for batch in portfolio)
        completed_backtests = 0
        cprint(
            f"Backtesting: {self.strategyName}_{self.version} UID: {self.fileDirUid}", "green")
        print(colored("Backtesting 0% complete.", "light_yellow"), end="\r")

        for batch in portfolio:
            processes = []
            for stock in batch:
                p = multiprocessing.Process(
                    target=self.backtestStock, args=(stock, startDate, endDate))
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

    def backtestStock(self, stockName, startDate, endDate):
        startTimeEpoch = startDate.timestamp()
        endTimeEpoch = endDate.timestamp()

        try:
            # Subtracting 31540000 to subtract 1 year from startTimeEpoch
            df_1d = getEquityBacktestData(
                stockName, startTimeEpoch-31540000, endTimeEpoch, "D")
            # Subtracting 864000 to subtract 10 days from startTimeEpoch
            df_15m = getEquityBacktestData(
                stockName, startTimeEpoch-864000, endTimeEpoch, "2H")
        except Exception as e:
            raise Exception(e)

        try:
            df_15m.dropna(inplace=True)
            df_1d.dropna(inplace=True)
        except:
            self.strategyLogger.info(f"Data not found for {stockName}")
            return

        df_1d["ti"] = df_1d["ti"] + 33300

        df_15m.set_index("ti", inplace=True)
        df_1d.set_index("ti", inplace=True)

        df_1d["ema10"] = talib.EMA(df_1d["c"], timeperiod=10)
        df_1d["ema110"] = talib.EMA(df_1d["c"], timeperiod=50)

        df_15m["plus_di"] = talib.PLUS_DI(
            df_15m["h"], df_15m["l"], df_15m["c"], timeperiod=14)
        df_15m["minus_di"] = talib.MINUS_DI(
            df_15m["h"], df_15m["l"], df_15m["c"], timeperiod=14)

        df_15m["rsi"] = talib.RSI(df_15m["c"], timeperiod=14)

        df_15m["diPlusCross"] = np.where((df_15m["plus_di"] >= di_cross) & (
            df_15m["plus_di"].shift(1) < di_cross), 1, 0)
        df_15m["diMinusCross"] = np.where((df_15m["minus_di"] >= di_cross) & (
            df_15m["minus_di"].shift(1) < di_cross), 1, 0)

        df_15m["rsiLongCross"] = np.where((df_15m["rsi"] >= rsi_upperBand) & (df_15m["rsi"].shift(
            1) < rsi_upperBand), 1, np.where((df_15m["rsi"] <= rsi_upperBand) & (df_15m["rsi"].shift(1) > rsi_upperBand), -1, 0))
        df_15m["rsiShortCross"] = np.where((df_15m["rsi"] <= rsi_lowerBand) & (df_15m["rsi"].shift(
            1) > rsi_lowerBand), 1, np.where((df_15m["rsi"] >= rsi_lowerBand) & (df_15m["rsi"].shift(1) < rsi_lowerBand), -1, 0))

        df_15m.dropna(inplace=True)
        df_1d.dropna(inplace=True)

        for day in range(0, (endDate - startDate).days, 5):
            threads = []
            for i in range(5):
                currentDate = (
                    startDate + timedelta(days=(day+i)))

                startDatetime = datetime.combine(
                    currentDate.date(), time(9, 15, 0))
                endDatetime = datetime.combine(
                    currentDate.date(), time(15, 30, 0))

                startEpoch = startDatetime.timestamp()
                endEpoch = endDatetime.timestamp()

                currentDate15MinDf = df_15m[(df_15m.index >= startEpoch) & (
                    df_15m.index <= endEpoch)].copy(deep=True)
                if currentDate15MinDf.empty:
                    continue

                df1DBeforeCurrentDate = df_1d[df_1d.index <= endEpoch]
                try:
                    trend = 1 if df1DBeforeCurrentDate.at[df1DBeforeCurrentDate.index[-2],
                                                          "ema10"] > df1DBeforeCurrentDate.at[df1DBeforeCurrentDate.index[-2], "ema110"] else -1
                except Exception as e:
                    trend = 0

                t = threading.Thread(
                    target=self.backtestDay, args=(stockName, startDatetime, endDatetime, currentDate15MinDf, trend))
                t.start()
                threads.append(t)

            for t in threads:
                t.join()

    def backtestDay(self, stockName, startDate, endDate, df, trend):
        # Set start and end timestamps for data retrieval
        startTimeEpoch = startDate.timestamp()
        endTimeEpoch = endDate.timestamp()

        stockAlgoLogic = equityIntradayAlgoLogic(stockName, self.fileDir)
        stockAlgoLogic.humanTime = startDate

        logger = setup_logger(
            f"{stockName}_{stockAlgoLogic.humanTime.date()}", f"{stockAlgoLogic.fileDir['backtestResultsStrategyLogs']}{stockName}_{stockAlgoLogic.humanTime.date()}_log.log",)
        logger.propagate = False

        df.to_csv(
            f"{stockAlgoLogic.fileDir['backtestResultsCandleData']}{stockName}_{stockAlgoLogic.humanTime.date()}_df.csv")

        amountPerTrade = 100000
        lastIndexTimeData = [0, 0]

        for timeData in df.index:
            stockAlgoLogic.timeData = timeData
            stockAlgoLogic.humanTime = datetime.fromtimestamp(timeData)

            if lastIndexTimeData[1] in df.index:
                logger.info(
                    f"Datetime: {stockAlgoLogic.humanTime}\tStock: {stockName}\tClose: {df.at[lastIndexTimeData[1],'c']}\tTrend: {trend}")

            if not stockAlgoLogic.openPnl.empty:
                for index, row in stockAlgoLogic.openPnl.iterrows():
                    stockAlgoLogic.openPnl.at[index,
                                              "CurrentPrice"] = df.at[lastIndexTimeData[1], "c"]

            stockAlgoLogic.pnlCalculator()

            for index, row in stockAlgoLogic.openPnl.iterrows():
                if stockAlgoLogic.humanTime.time() >= time(15, 15):
                    exitType = "Time Up"
                    stockAlgoLogic.exitOrder(index, exitType)
                elif row["PositionStatus"] == 1:
                    if df.at[lastIndexTimeData[1], "l"] <= (0.995*row["EntryPrice"]):
                        exitType = "Stoploss Hit"
                        stockAlgoLogic.exitOrder(
                            index, exitType, (0.995*row["EntryPrice"]))
                elif row["PositionStatus"] == -1:
                    if df.at[lastIndexTimeData[1], "h"] >= (1.005*row["EntryPrice"]):
                        exitType = "Stoploss Hit"
                        stockAlgoLogic.exitOrder(
                            index, exitType, (1.005*row["EntryPrice"]))

            if (stockAlgoLogic.openPnl.empty & stockAlgoLogic.closedPnl.empty) & (lastIndexTimeData[0] in df.index) & (lastIndexTimeData[1] in df.index) & (stockAlgoLogic.humanTime.time() > time(9, 45)) & (stockAlgoLogic.humanTime.time() < time(15, 15)):
                if trend == 1:
                    if (df.at[lastIndexTimeData[0], "plus_di"] >= 30) & (df.at[lastIndexTimeData[0], "rsiLongCross"] == 1) & (df.at[lastIndexTimeData[1], "plus_di"] >= 30) & (df.at[lastIndexTimeData[1], "rsi"] >= rsi_upperBand):
                        entry_price = df.at[lastIndexTimeData[1], "c"]
                        stockAlgoLogic.entryOrder(
                            entry_price, stockName,  (amountPerTrade//entry_price), "BUY")
                    elif (df.at[lastIndexTimeData[0], "rsi"] >= rsi_upperBand) & (df.at[lastIndexTimeData[0], "diPlusCross"] == 1) & (df.at[lastIndexTimeData[1], "plus_di"] >= 30) & (df.at[lastIndexTimeData[1], "rsi"] >= rsi_upperBand):
                        entry_price = df.at[lastIndexTimeData[1], "c"]
                        stockAlgoLogic.entryOrder(
                            entry_price, stockName, (amountPerTrade//entry_price), "BUY")
                elif trend == -1:
                    if (df.at[lastIndexTimeData[0], "minus_di"] >= 30) & (df.at[lastIndexTimeData[0], "rsiShortCross"] == 1) & (df.at[lastIndexTimeData[1], "minus_di"] >= 30) & (df.at[lastIndexTimeData[1], "rsi"] <= rsi_lowerBand):
                        entry_price = df.at[lastIndexTimeData[1], "c"]
                        stockAlgoLogic.entryOrder(entry_price, stockName,
                                                  (amountPerTrade//entry_price), "SELL")
                    elif (df.at[lastIndexTimeData[0], "rsi"] <= rsi_lowerBand) & (df.at[lastIndexTimeData[0], "diMinusCross"] == 1) & (df.at[lastIndexTimeData[1], "minus_di"] >= 30) & (df.at[lastIndexTimeData[1], "rsi"] <= rsi_lowerBand):
                        entry_price = df.at[lastIndexTimeData[1], "c"]
                        stockAlgoLogic.entryOrder(entry_price, stockName,
                                                  (amountPerTrade//entry_price), "SELL")

            lastIndexTimeData.pop(0)
            lastIndexTimeData.append(timeData)
            stockAlgoLogic.pnlCalculator()
