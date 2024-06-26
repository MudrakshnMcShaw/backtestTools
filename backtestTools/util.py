import json
import logging
import pandas as pd
from datetime import time, timedelta
from backtestTools.histData import (getEquityBacktestData, getFnoBacktestData,)


def setup_logger(name, log_file, level=logging.INFO, formatter=logging.Formatter("%(message)s")):
    """
    Set up a logger with a specified name, log file, and logging level.

    Parameters:
        name (string): The name of the logger.

        log_file (string): The path to the log file.

        level (int): The logging level (default is logging.INFO).

    Returns:
        logging.Logger: The configured logger object.

    Example:
    ```
        logger = setup_logger('my_logger', 'example.log')
        logger.info('This is an information message.')
    ```
    """

    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logging.basicConfig(level=level, filemode="a", force=True)

    return logger


def createPortfolio(filename, stocksPerProcess=4):
    """
    Create a portfolio from a file containing stock symbols seperated by newline.

    Parameters:
        filename (string): The path to the file containing stock symbols.

        stocksPerProcess (int): The number of stocks per sublist (default is 4).

    Returns:
        list: A list of 'stocksPerProcess' number of sublists, each containing stock symbols.

    Example:
    ```
        portfolio = createPortfolio('stocks.txt', stocksPerProcess=5)s
        print(portfolio)
    ```
    """
    portfolio = []

    with open(filename, "r") as file:
        elements = [line.strip() for line in file]

    # Create sublists with four elements each
    t = len(elements) // stocksPerProcess
    stocksPerSublist = len(elements) // t
    for i in range(0, t):
        if i < (t - 1):
            sublist = elements[i *
                               stocksPerSublist:(i * stocksPerSublist) + stocksPerSublist]
            portfolio.append(sublist)
        else:
            sublist = elements[i * stocksPerSublist:len(elements)]
            portfolio.append(sublist)

    logging.info(f"Portfolio created: {portfolio}")

    return portfolio


# Add code to calculate daily report for options strategy
def calculateDailyReport(closedPnl, saveFileDir, timeFrame=timedelta(minutes=1), mtm=False, fno=True):
    """
    Calculates the daily report for an options trading strategy based on the closed trades.

    Parameters:
        closedPnl (DataFrame): DataFrame containing information about closed trades.

        saveFileDir (str): Directory path where the daily report CSV file will be saved.

        timeFrame (timedelta, optional): Time frame for each period in the daily report. Default is 1 minute.

        mtm (bool, optional): Flag indicating whether mark-to-market (MTM) calculation should be performed. Default is False.

        fno (bool, optional): Flag indicating whether the strategy involves trading in futures and options (F&O). Default is True.

    Returns:
        dailyReport (DataFrame): DataFrame containing the calculated daily report.

    """
    # Initialize daily report DataFrame
    closedPnl["Key"] = pd.to_datetime(closedPnl["Key"])
    closedPnl["ExitTime"] = pd.to_datetime(closedPnl["ExitTime"])

    # startDatetime = closedPnl["Key"].iloc[0].to_pydatetime()
    # endDatetime = (closedPnl["ExitTime"].iloc[-1].to_pydatetime()) + timeFrame + timeFrame

    startDatetime = closedPnl["Key"].min(
    ).to_pydatetime().replace(hour=9, minute=15)
    endDatetime = (closedPnl["ExitTime"].max().to_pydatetime()) + timeFrame

    dailyReport = pd.DataFrame(
        columns=["Date", "OpenTrades", "CapitalInvested", "CumulativePnl", "mtmPnl"])

    symbolDF = {}
    if fno:
        for symbol in closedPnl["Symbol"].unique():
            symbolDF[symbol] = getFnoBacktestData(
                symbol, startDatetime, endDatetime, "1Min")
    else:
        for symbol in closedPnl["Symbol"].unique():
            symbolDF[symbol] = getEquityBacktestData(
                symbol, startDatetime, endDatetime, "1Min")

    lastCumulativePnl = 0
    lastPnlForMtmCal = 0
    currentDatetime = startDatetime

    # Loop through each day within the specified date range
    while currentDatetime <= endDatetime:
        cumulativePnl = 0

        # nextDate = currentDate+timedelta(days=1)
        nextDatetime = currentDatetime + timeFrame

        if currentDatetime.date() != nextDatetime.date():
            lastPnlForMtmCal = lastCumulativePnl

        # Skip weekends and non-trading hours
        if ((currentDatetime.time() < time(9, 15)) | (currentDatetime.time() > time(15, 30)) | (currentDatetime.weekday() in [5, 6])):
            currentDatetime = nextDatetime
            continue

        # Calculate pnl for closed trades
        closedTrades = closedPnl[(closedPnl["Key"] < nextDatetime) & (
            closedPnl["ExitTime"] < nextDatetime)]
        cumulativePnl += closedTrades["Pnl"].sum()

        # Calculate capital invested for open trades
        openTrades = closedPnl[(closedPnl["Key"] < nextDatetime) & (
            closedPnl["ExitTime"] >= nextDatetime)]
        # capitalInvested = (openTrades["EntryPrice"]
        #                    * openTrades["Quantity"]).sum()

        if fno:
            nakedSell = 0
            spread = 0
            nakedBuy = 0
            nakedBuyIndex = []
            for index, row in openTrades.iterrows():
                if row['PositionStatus'] == -1:
                    if nakedBuy > 0:
                        spread += 1
                        nakedBuy -= 1
                        nakedBuyIndex.pop(0)
                        continue

                    nakedSell += 1

                elif row['PositionStatus'] == 1:
                    if nakedSell > 0:
                        spread += 1
                        nakedSell -= 1
                        continue

                    nakedBuy += 1
                    nakedBuyIndex.append(index)
                    # nakedBuyMargin += row['EntryPrice']

            capitalInvested = (nakedSell * 100000) + (spread * 30000)

            if nakedBuyIndex:
                for i in nakedBuyIndex:
                    capitalInvested += openTrades.at[i,
                                                     "EntryPrice"] * openTrades.at[i, "Quantity"]
        else:
            capitalInvested = (
                openTrades["EntryPrice"] * openTrades["Quantity"]).sum()

        # Perform mark-to-market calculation if required
        if mtm:
            for symbol in openTrades["Symbol"].unique():
                try:
                    if fno:
                        currentData = symbolDF[symbol].loc[currentDatetime.timestamp(
                        )]
                    else:
                        currentData = symbolDF[symbol].loc[
                            currentDatetime.timestamp()]
                    if currentData is None:
                        cumulativePnl = lastCumulativePnl
                        break
                except:
                    cumulativePnl = lastCumulativePnl
                    break

                symbolOpenTrades = openTrades[openTrades["Symbol"] == symbol].copy(
                    deep=True)
                symbolOpenTrades["Pnl"] = (
                    currentData["o"] - symbolOpenTrades["EntryPrice"]) * symbolOpenTrades["Quantity"] * symbolOpenTrades["PositionStatus"]
                cumulativePnl += symbolOpenTrades["Pnl"].sum()

        # Update daily report DataFrame
        currentEntryData = pd.DataFrame(
            {
                "Date": currentDatetime,
                "OpenTrades": len(openTrades),
                "CapitalInvested": capitalInvested,
                "CumulativePnl": cumulativePnl,
                "mtmPnl": cumulativePnl - lastPnlForMtmCal,
            },
            index=[0],
        )

        dailyReport = pd.concat(
            [dailyReport, currentEntryData], ignore_index=True)

        lastCumulativePnl = cumulativePnl
        currentDatetime = nextDatetime

        # Save and print progress
        progress_percentage = (
            (currentDatetime - startDatetime) / (endDatetime - startDatetime)) * 100
        print(f"Progress: {progress_percentage:.2f}%", end="\r")
        # dailyReport.to_csv(f"{saveFileDir}/dailyReport.csv")

    # Calculate peak and drawdown
    dailyReport["Peak"] = dailyReport["CumulativePnl"].cummax()
    dailyReport["Drawdown"] = dailyReport["CumulativePnl"] - \
        dailyReport["Peak"]

    # dailyReport["mtmPnl"] = dailyReport["CumulativePnl"].diff()
    saveFileSplit = saveFileDir.split('/')[::-1]
    saveFileSplitLen = len(saveFileSplit)
    saveFile = None
    for i in range(saveFileSplitLen):
        if '_' in saveFileSplit[i]:
            saveFile = '_'.join(saveFileSplit[:i+1][::-1])
            break

    if saveFile is None:
        saveFile = saveFileDir.split('/')[-1]

    dailyReport.to_csv(f"{saveFileDir}/mtm_{saveFile}.csv")
    print("dailyReport.csv saved")

    closedPnlCopy = closedPnl.copy(deep=True)

    for col in closedPnlCopy.select_dtypes(include=['datetime64[ns]']):
        closedPnlCopy[col] = closedPnlCopy[col].dt.strftime(
            '%Y-%m-%d %H:%M:%S')  # ISO 8601 format

    for col in dailyReport.select_dtypes(include=['datetime64[ns]']):
        dailyReport[col] = dailyReport[col].dt.strftime(
            '%Y-%m-%d %H:%M:%S')  # ISO 8601 format

    merged_data = {}

    # Add data from each DataFrame to the dictionary with appropriate keys
    merged_data["closedPnl"] = closedPnlCopy.to_dict(orient='records')
    merged_data["mtm"] = dailyReport.to_dict(orient='records')

    # Convert dictionary to JSON string
    json_data = json.dumps(merged_data)

    # Write JSON data to a file (optional)
    # with open(f"{saveFileDir}/backtestEngine.json", "w") as outfile:
    with open(f"{saveFileDir}/{saveFile}.json", "w") as outfile:
        outfile.write(json_data)

    return dailyReport


def limitCapital(originalClosedPnl, saveFileDir, maxCapitalAmount):
    """
    Limits the capital invested in open trades to a specified maximum amount.

    Parameters:
        originalClosedPnl (DataFrame): DataFrame containing information about closed trades.

        saveFileDir (str): Directory path where the modified closed trades CSV file will be saved.

        maxCapitalAmount (float): Maximum amount of capital allowed to be invested in open trades.

    Returns:
        closedPnl (DataFrame): DataFrame containing the modified closed trades after limiting capital.
    """
    closedPnl = originalClosedPnl.copy(deep=True)

    # Initialize daily report DataFrame
    startDatetime = closedPnl["Key"].iloc[0].to_pydatetime()
    endDatetime = closedPnl["Key"].iloc[-1].to_pydatetime()

    startDate = startDatetime.date()
    endDate = endDatetime.date() + timedelta(days=10)

    currentDate = startDate

    while currentDate <= endDate:
        nextDate = currentDate + timedelta(days=1)

        # Filter open trades and calculate capital invested
        openTrades = closedPnl[(closedPnl["Key"].dt.date < nextDate) & (
            closedPnl["ExitTime"].dt.date >= nextDate)]
        capitalInvested = (openTrades["EntryPrice"]
                           * openTrades["Quantity"]).sum()

        # Fix capital and drop extra trades for which more capital is required
        while capitalInvested > maxCapitalAmount:
            closedPnl.drop(openTrades.index[-1], inplace=True)
            closedPnl.reset_index(inplace=True, drop=True)

            openTrades = closedPnl[(closedPnl["Key"].dt.date < nextDate) & (
                closedPnl["ExitTime"].dt.date >= nextDate)]

            capitalInvested = (
                openTrades["EntryPrice"] * openTrades["Quantity"]).sum()

        currentDate = nextDate

    closedPnl.to_csv(f"{saveFileDir}/closedPnlFixCap.csv")
    print("closedPnlFixCap.csv saved.")

    return closedPnl


def generateReportFile(dailyReport, saveFileDir):
    """
    Generates a report summary based on the daily report DataFrame and saves it to a text file.

    Parameters:
        dailyReport (DataFrame): DataFrame containing the daily report information.

        saveFileDir (str): Directory path where the report text file will be saved.

    Returns:
        max_drawdown_percentage (float): Maximum drawdown percentage calculated based on the report.
    """
    # Generate and save report summary to a text file
    reportFile = open(f"{saveFileDir}report.txt", "w")

    dailyReport = dailyReport[dailyReport["CapitalInvested"] != 0]

    reportFile.write(
        f"Maximum Capital Invested: {dailyReport['CapitalInvested'].max()}\n")
    reportFile.write(
        f"Mean Capital Invested: {dailyReport['CapitalInvested'].mean()}\n")
    reportFile.write(
        f"Median Capital Invested: {dailyReport['CapitalInvested'].median()}\n\n\n"
    )

    max_drawdown = dailyReport["Drawdown"].min()
    peak_value = dailyReport[dailyReport["Drawdown"]
                             == max_drawdown]["Peak"].max()
    max_drawdown_cap_invested = dailyReport[dailyReport["Drawdown"]
                                            == max_drawdown]["CapitalInvested"].max()

    max_drawdown_percentage = (max_drawdown / peak_value) * 100
    max_drawdown_mean_capital = (
        max_drawdown / dailyReport["CapitalInvested"].mean()) * 100

    reportFile.write(f"Maximum Drawdown: {max_drawdown}\n")
    reportFile.write(
        f"Peak Value used for maximum drawdown calculation: {peak_value}\n\n")
    reportFile.write(
        f"Capital Invested during maximum drawdown calculation: {max_drawdown_cap_invested}\n\n")

    reportFile.write(
        f"Maximum Drawdown Percentage (Mean Cap): {max_drawdown_mean_capital}\n")
    reportFile.write(
        f"Maximum Drawdown Percentage (Peak): {max_drawdown_percentage}\n\n")

    reportFile.close()
    print("report.txt saved.")

    return max_drawdown_percentage
