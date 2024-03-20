import logging
import numpy as np
import talib as ta
from backtestTools.expiry import getExpiryData
from datetime import datetime, time
from backtestTools.algoLogic import optOverNightAlgoLogic
from backtestTools.histData import getFnoHistData, getFnoBacktestData


# Define a class algoLogic that inherits from optOverNightAlgoLogic
class algoLogic(optOverNightAlgoLogic):

    # Define a method to get current expiry epoch
    def getCurrentExpiryEpoch(self, date, baseSym):
        # Fetch expiry data for current and next expiry
        expiryData = getExpiryData(date, baseSym)
        nextExpiryData = getExpiryData(date+86400, baseSym)

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
        col = ["Target", "Stoploss", "Expiry"]
        self.addColumnsToOpenPnlDf(col)

        # Convert start and end dates to timestamps
        startEpoch = startDate.timestamp()
        endEpoch = endDate.timestamp()

        try:
            # Fetch historical data for backtesting
            df = getFnoBacktestData(indexSym, startEpoch, endEpoch, "1Min")
        except Exception as e:
            # Log an exception if data retrieval fails
            logging.info(
                f"Data not found for {baseSym} in range {startDate} to {endDate}")
            raise Exception(e)

        # Drop rows with missing values
        df.dropna(inplace=True)

        # Calculate EMA indicators
        df["ema10"] = ta.EMA(df["c"], timeperiod=10)
        df["ema20"] = ta.EMA(df["c"], timeperiod=20)

        # Determine crossover signals
        df["crossOver"] = np.where((df["ema10"] > df["ema20"]) & (df["ema10"].shift(1) <= df["ema20"].shift(
            1)), 1, (np.where((df["ema10"] < df["ema20"]) & (df["ema10"].shift(1) >= df["ema20"].shift(1)), -1, 0)))

        df.to_csv(
            f"{self.fileDir['backtestResultsCandleData']}{indexName}_1Min.csv")

        # Strategy Parameters
        lastIndexTimeData = [0, 0]

        # Loop through each timestamp in the DataFrame index
        for timeData in df.index:
            self.timeData = float(timeData)
            self.humanTime = datetime.fromtimestamp(timeData)

            # Skip time periods outside trading hours
            if (self.humanTime.time() < time(9, 16)) | (self.humanTime.time() > time(15, 30)):
                continue

            # Update lastIndexTimeData
            lastIndexTimeData.pop(0)
            lastIndexTimeData.append(timeData-60)

            # Log relevant information
            if lastIndexTimeData[1] in df.index:
                logging.info(
                    f"Datetime: {self.humanTime}\tClose: {df.at[lastIndexTimeData[1],'c']}\tEMA10: {df.at[lastIndexTimeData[1],'ema10']}\tEMA20: {df.at[lastIndexTimeData[1],'ema20']}")

            # Update current price for open positions
            if not self.openPnl.empty:
                for index, row in self.openPnl.iterrows():
                    try:
                        data = getFnoHistData(
                            row['Symbol'], lastIndexTimeData[1])
                        self.openPnl.at[index, 'CurrentPrice'] = data['c']
                    except Exception as e:
                        logging.info(e)

            # Calculate and update PnL
            self.pnlCalculator()

            # Check and execute exit orders
            if not self.openPnl.empty:
                for index, row in self.openPnl.iterrows():

                    symSide = row["Symbol"]
                    symSide = symSide[len(symSide)-2:]

                    if (df.at[lastIndexTimeData[1], "crossOver"] == 1) & (symSide == "CE"):
                        exitType = "+ve Crossover Hit"
                        self.exitOrder(index, exitType)
                    elif (df.at[lastIndexTimeData[1], "crossOver"] == -1) & (symSide == "PE"):
                        exitType = "-ve Crossover Hit"
                        self.exitOrder(index, exitType)
                    elif row["CurrentPrice"] <= row["Target"]:
                        exitType = "Call Target Hit"
                        self.exitOrder(index, exitType, row["Target"])
                    elif row["CurrentPrice"] >= row["Stoploss"]:
                        exitType = "Call Stoploss Hit"
                        self.exitOrder(index, exitType, row["Stoploss"])
                    elif self.timeData >= row["Expiry"]:
                        exitType = "Call Time Up"
                        self.exitOrder(index, exitType)

            # Check for entry signals and execute orders
            if (lastIndexTimeData[1] in df.index):
                if len(self.openPnl) < 1:
                    if df.at[lastIndexTimeData[1], "crossOver"] == 1:
                        putSym = self.getPutSym(
                            self.timeData, baseSym, df.at[lastIndexTimeData[1], "c"])
                        expiryEpoch = self.getCurrentExpiryEpoch(
                            self.timeData, baseSym)
                        lotSize = int(getExpiryData(
                            self.timeData, baseSym)["LotSize"])

                        try:
                            data = getFnoHistData(
                                putSym, lastIndexTimeData[1])
                        except Exception as e:
                            logging.info(e)

                        self.entryOrder(data['c'], putSym, lotSize, "SELL",
                                        {"Target": (0.5 * data['c']), "Stoploss": (1.3 * data['c']), "Expiry": expiryEpoch})

                    elif df.at[lastIndexTimeData[1], "crossOver"] == -1:
                        callSym = self.getCallSym(
                            self.timeData, baseSym, df.at[lastIndexTimeData[1], "c"])
                        expiryEpoch = self.getCurrentExpiryEpoch(
                            self.timeData, baseSym)
                        lotSize = int(getExpiryData(
                            self.timeData, baseSym)["LotSize"])

                        try:
                            data = getFnoHistData(
                                callSym, lastIndexTimeData[1])
                        except Exception as e:
                            logging.info(e)

                        self.entryOrder(data['c'], callSym, lotSize, "SELL",
                                        {"Target": (0.5 * data['c']), "Stoploss": (1.3 * data['c']), "Expiry": expiryEpoch})

        # Calculate final PnL and combine CSVs
        self.pnlCalculator()
        self.combinePnlCsv()


if __name__ == "__main__":
    # Define Strategy Nomenclature
    devName = "NA"
    strategyName = "optEma"
    version = "v4"

    # Define Start date and End date
    startDate = datetime(2021, 1, 5, 9, 15)
    endDate = datetime(2021, 1, 7, 15, 30)

    # Create algoLogic object
    algo = algoLogic(devName, strategyName, version)

    # Define Index Name
    baseSym = 'NIFTY'
    indexName = 'NIFTY 50'

    # Execute the algorithm
    algo.run(startDate, endDate, baseSym, indexName)
