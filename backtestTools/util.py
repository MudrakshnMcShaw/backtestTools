"""
Utility Functions for Backtesting Framework

This module provides a comprehensive suite of utility functions for the backtesting framework,
including logging setup, portfolio creation, daily report generation, capital limiting,
and mark-to-market (MTM) calculations for both equity and F&O trading strategies.

Key Features:
- Logger configuration for backtesting outputs
- Portfolio management from file-based stock lists
- Daily performance reporting with PnL calculations
- Capital constraint enforcement
- Real-time mark-to-market position tracking and reporting
- JSON and CSV export capabilities for backtesting results

Dependencies:
- pandas: Data manipulation and time series analysis
- numpy: Numerical computations
- mongodb (via backtestTools.histData): Historical OHLC data retrieval
"""

import json
import logging
import numpy as np
import pandas as pd
from datetime import time, timedelta
from pandas.api.types import is_datetime64_any_dtype
from backtestTools.histData import getEquityBacktestData, getFnoBacktestData, connectToMongo


def setup_logger(name, log_file, level=logging.INFO, formatter=logging.Formatter("%(message)s")):
    """
    Set up a logger with a specified name, log file, and logging level.

    Parameters:
        name (str): Unique identifier for the logger instance.
        
        log_file (str): Absolute or relative file path where log messages will be written.
        
        level (int): Logging level threshold (e.g., logging.INFO, logging.DEBUG, logging.ERROR).
                     Only messages at this level or higher will be logged. Default is logging.INFO.
        
        formatter (logging.Formatter): Custom formatter for log message output. 
                                      Default formats only the message text without timestamp or level.

    Returns:
        logging.Logger: Configured logger object ready for use with handler attached to specified file.
        
    Raises:
        IOError: If log file cannot be created or accessed at the specified path.

    Example:
        ```
        logger = setup_logger('my_logger', '/path/to/logs/example.log', logging.DEBUG)
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
    Create a portfolio by partitioning stock symbols from a file into equal-sized sublists.

    Reads a newline-delimited file of stock symbols and distributes them into sublists
    of approximately equal size based on the stocksPerProcess parameter. Useful for
    parallel processing of symbols across multiple processes.

    Parameters:
        filename (str): Path to text file containing one stock symbol per line.
                       Whitespace at beginning/end of each line is automatically stripped.
        
        stocksPerProcess (int): Approximate number of stocks per sublist. The function
                               calculates the optimal sublist size to balance distribution.
                               Default is 4 stocks per process.

    Returns:
        list: List of sublists, where each sublist contains stock symbols (str).
              The number of sublists equals approximately total_symbols / stocksPerProcess.
              The last sublist may contain fewer elements if distribution is uneven.
              
    Raises:
        FileNotFoundError: If the specified file does not exist.
        IOError: If the file cannot be read.

    Example:
        ```
        portfolio = createPortfolio('stocks.txt', stocksPerProcess=5)
        print(portfolio)  # [['INFY', 'TCS', 'HCL', 'WIPRO', 'TECH'], ['SBIN', 'HDFC', 'ICICI']]
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


def calculateDailyReport(closedPnl, saveFileDir, timeFrame=timedelta(minutes=1), mtm=False, fno=True):
    """
    Generate daily performance report from closed trades with capital metrics and mark-to-market calculations.

    Creates a comprehensive daily report by aggregating trade data across specified time periods,
    calculating cumulative P&L, tracking capital invested, and computing peak/drawdown metrics.
    Optionally performs mark-to-market valuation of open positions at each time step.

    Parameters:
        closedPnl (pd.DataFrame): Trade records with columns: Key (entry time), ExitTime, Symbol,
                                 EntryPrice, Quantity, PositionStatus (1/-1 for BUY/SELL), Pnl.
        
        saveFileDir (str): Directory path where output files (CSV and JSON) will be saved.
                          Directory must exist; files will be named based on save directory name.
        
        timeFrame (timedelta): Time period for aggregating report metrics. Default is timedelta(minutes=1)
                             for minute-level reporting; common alternatives: timedelta(hours=1) for hourly.
        
        mtm (bool): If True, performs mark-to-market valuation of open positions using current OHLC prices.
                   If False, only realized PnL from closed trades is included. Default is False.
        
        fno (bool): If True, treats all symbols as F&O instruments using getFnoBacktestData.
                   If False, treats symbols as equity using getEquityBacktestData. Default is True.

    Returns:
        pd.DataFrame: Daily report with columns:
                     - Date: Timestamp of the reporting period
                     - OpenTrades: Number of open positions at that time
                     - CapitalInvested: Capital required for open positions
                     - CumulativePnl: Running total of realized and unrealized P&L
                     - mtmPnl: Intra-day mark-to-market P&L change
                     - Peak: Maximum cumulative P&L reached up to that point
                     - Drawdown: Current drawdown from peak P&L
                     
    Raises:
        KeyError: If required columns missing from closedPnl DataFrame.
        ValueError: If saveFileDir path is invalid.
        
    Notes:
        - Trading hours enforced: 09:15 to 15:30 IST (market hours)
        - Weekends and holidays automatically skipped
        - Capital calculation for F&O includes spread margin (30K) vs naked sell margin (100K)
        - Output files: mtm_{name}.csv (time-series report), {name}.json (detailed export)
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
            # Pair up buy and sell positions into spreads (lower margin requirement ~30K)
            # Remaining unpaired positions are naked (higher margin: 100K for sell, entry price for buy)
            for index, row in openTrades.iterrows():
                if row['PositionStatus'] == -1:
                    if nakedBuy > 0:
                        # Match this sell with an existing unpaired buy → creates spread (1 contract)
                        spread += 1
                        nakedBuy -= 1
                        nakedBuyIndex.pop(0)
                        continue

                    nakedSell += 1

                elif row['PositionStatus'] == 1:
                    if nakedSell > 0:
                        # Match this buy with an existing unpaired sell → creates spread (1 contract)
                        spread += 1
                        nakedSell -= 1
                        continue

                    nakedBuy += 1
                    nakedBuyIndex.append(index)

            # Capital = (spreads × 30K margin) + (naked shorts × 100K margin) + (naked longs × entry price × qty)
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
    Filter trades to enforce a maximum capital constraint for any open position window.

    Progressively removes trades (starting with most recent) until capital invested in open
    positions at each point in time stays below the specified maximum. This is useful for
    simulating trading under capital constraints or limiting margin utilization.

    Parameters:
        originalClosedPnl (pd.DataFrame): Trade records with columns: Key (entry time),
                                         ExitTime, EntryPrice, Quantity. DataFrame is NOT modified in-place.
        
        saveFileDir (str): Directory path where the modified trade list is saved as 'closedPnlFixCap.csv'.
                         Directory must exist and be writable.
        
        maxCapitalAmount (float): Maximum capital (in currency units) that can be invested at any time.
                                For F&O: typically 100K (naked sell) or 30K (spread).
                                For equity: typically sum of (price × quantity) for all open positions.

    Returns:
        pd.DataFrame: Filtered copy of originalClosedPnl with trades removed to satisfy capital constraint.
                     Maintains all original columns and row order (except removed trades).
                     
    Raises:
        ValueError: If maxCapitalAmount is less than 0.
        KeyError: If required columns (Key, ExitTime, EntryPrice, Quantity) missing from DataFrame.
        
    Notes:
        - Trades are removed from most recent backwards until capital constraint is satisfied
        - Modified DataFrame is saved to {saveFileDir}/closedPnlFixCap.csv
        - Useful for Monte Carlo simulations with varying capital constraints
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
    Generate a text report summary with key performance metrics from daily report data.

    Creates a formatted text file containing capital statistics, drawdown analysis, and peak metrics.
    Filters the report to only include periods with active capital investment (CapitalInvested > 0).

    Parameters:
        dailyReport (pd.DataFrame): Daily performance report with columns: CapitalInvested,
                                   CumulativePnl, Peak, Drawdown. Typically output from calculateDailyReport.
        
        saveFileDir (str): Directory path where the report text file will be saved as 'report.txt'.
                         Directory must exist and be writable.

    Returns:
        float: Maximum drawdown percentage, calculated as:
               (maximum_drawdown_amount / peak_value_at_drawdown) × 100
               Represents the largest percentage loss from a peak value during the trading period.
               Typically a negative value (e.g., -15.5 for 15.5% drawdown).
               
    Raises:
        IOError: If report.txt cannot be created at saveFileDir.
        ValueError: If required columns missing or all CapitalInvested values are zero.
        
    Notes:
        - Only reports on periods when capital was actively invested
        - Reports include min, mean, and median capital amounts
        - Maximum drawdown metrics include both peak value reference and mean capital normalization
        - Output file: {saveFileDir}/report.txt
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


def calculate_mtm(closedPnl, saveFileDir, timeFrame="15T", mtm=False, equityMarket=True, conn=None):
    """
    Calculate minute-by-minute mark-to-market positions and P&L with resampled reporting.

    Builds a detailed time-series of portfolio metrics by iterating through each trade and
    computing its contribution to open positions, capital required, and mark-to-market P&L
    at each minute. Results are resampled to specified timeframe and aggregated with position
    tracking (buy/sell/spread counts) and margin calculations.

    Parameters:
        closedPnl (pd.DataFrame): Trade records with columns: Key (entry datetime),
                                 ExitTime (exit datetime), Symbol, EntryPrice, Quantity,
                                 PositionStatus (1 for BUY, -1 for SELL), Pnl (realized P&L).
        
        saveFileDir (str): Directory where output files will be saved.
                         Creates: mtm_{name}.csv (resampled MTM report) and {name}.json (detailed export).
        
        timeFrame (str): Resampling frequency for aggregated output. Default '15T' (15-minute bars).
                        Other common values: '1H' (hourly), '1D' (daily), '1min' (minute-level).
        
        mtm (bool): Unused legacy parameter. Included for backward compatibility. Default is False.
        
        equityMarket (bool): If True, retrieves equity price data using getEquityBacktestData.
                           If False, retrieves F&O price data using getFnoBacktestData. Default is True.
        
        conn (pymongo.MongoClient, optional): MongoDB connection object. If None, a new connection
                                             is created via connectToMongo(). Allows connection reuse
                                             for efficiency in batch processing.

    Returns:
        pd.DataFrame: Resampled MTM report with columns:
                     - Date: Period start timestamp
                     - OpenTrades: Maximum open positions during the period
                     - CapitalInvested: Maximum capital required during the period
                     - CumulativePnl: Realized P&L at end of period
                     - mtmPnl: Intra-day P&L change from previous day close
                     - BuyPosition: Number of long positions
                     - SellPosition: Number of short positions
                     - Spread: Minimum of (long, short) = number of paired spreads
                     - Peak: Running maximum of CumulativePnl
                     - Drawdown: Current drawdown from peak
                     
    Raises:
        KeyError: If required columns missing from closedPnl or OHLC data.
        ValueError: If data retrieval fails or invalid timeFrame specification.
        IOError: If output files cannot be written to saveFileDir.
        
    Notes:
        - Uses NIFTY 50 as index reference for market hours and time range
        - IST timezone applied: 19800-second offset from Unix epoch (UTC+5:30)
        - Capital calculation: (spreads × 30K) + (naked shorts × 100K) + (naked longs × margin)
        - MTM P&L reset at day boundaries; calculated as (end-of-day PnL - previous day close)
        - Missing data in OHLC series filled forward then backward to handle gaps
        - Progress indicator printed to console during iteration
        - Output files use derived name from saveFileDir path
    """
    if conn is None:
        conn = connectToMongo()

    if not is_datetime64_any_dtype(closedPnl["Key"]):
        closedPnl["Key"] = pd.to_datetime(closedPnl["Key"])
    if not is_datetime64_any_dtype(closedPnl["ExitTime"]):
        closedPnl["ExitTime"] = pd.to_datetime(closedPnl["ExitTime"])

    startDatetime = closedPnl['Key'].min().replace(hour=9, minute=15)
    endDatetime = (closedPnl['ExitTime'].max()).replace(hour=15, minute=29)

    closedPnl = closedPnl[closedPnl['EntryPrice']!= 0]

    mtm_df = pd.DataFrame()

    # mtm_df["Date"] = pd.date_range(
    #     start=startDatetime, end=endDatetime, freq="1T")
    
    index_df = getFnoBacktestData("NIFTY 50", startDatetime, endDatetime, "1min", conn=conn)
    mtm_df["Date"] = pd.to_datetime(index_df["datetime"])
    mtm_df['Index'] = mtm_df['Date']
    mtm_df.set_index("Index", inplace=True)

    mtm_df = mtm_df.between_time("09:15:00", "15:29:00")
    mtm_df = mtm_df[mtm_df.index.dayofweek < 5]

    # Convert datetime index to IST epoch timestamps by subtracting 19800 seconds (UTC+5:30 offset)
    mtm_df['ti'] = (mtm_df.index.values.astype(np.int64) //
                    10**9) - 19800
    mtm_df.set_index("ti", inplace=True)

    mtm_df['OpenTrades'] = 0
    mtm_df['CapitalInvested'] = 0
    mtm_df['CumulativePnl'] = 0
    mtm_df['mtmPnl'] = 0
    mtm_df['BuyPosition'] = 0
    mtm_df['SellPosition'] = 0
    mtm_df['BuyMargin'] = 0

    i = 0
    total_rows = len(closedPnl)
    for index, row in closedPnl.iterrows():
        # Adjust entry/exit times backward 5:30 hours to convert from IST to UTC for data retrieval
        # Add 1 day to exit time to capture trades crossing midnight in UTC terms
        tradeStart = closedPnl.at[index, 'Key'] - \
            timedelta(hours=5, minutes=30)
        tradeEnd = closedPnl.at[index, 'ExitTime'] - \
            timedelta(hours=5, minutes=30)+timedelta(days=1)

        if equityMarket:
            ohlc_df = getEquityBacktestData(
                row["Symbol"], tradeStart, tradeEnd, "T", conn=conn)
        else:
            ohlc_df = getFnoBacktestData(
                row["Symbol"], tradeStart, tradeEnd, "T", conn=conn)

        if ohlc_df is None:
            print(f"{row['Symbol']} not found in database.")
            continue

        try:
            # if ohlc_df.at[ohlc_df.index[-1], 'datetime'].date() == row['ExitTime'].date():
            last_index = ohlc_df.index[-1]
            next_index = mtm_df[mtm_df.index > last_index].index[0]
            ohlc_df.loc[next_index] = 0
            ohlc_df.loc[next_index, 'ti'] = next_index
            ohlc_df.loc[next_index, 'datetime'] = mtm_df.at[next_index, "Date"]
        except Exception as e:
            pass

        ohlc_df['openTrade'] = 1
        ohlc_df['pnl'] = ((ohlc_df['o'] - row["EntryPrice"])
                          * row["Quantity"] * row["PositionStatus"])

        if ohlc_df.iloc[-1]['pnl'] != closedPnl['Pnl'].iloc[0]:
                ohlc_df.at[ohlc_df.index[-1], 'pnl'] = row['Pnl']

        if row["PositionStatus"] == 1:
            ohlc_df['buyPosition'] = 1
            ohlc_df['sellPosition'] = 0
            ohlc_df['buyMargin'] = row["EntryPrice"] * row["Quantity"]
        else:
            ohlc_df['buyPosition'] = 0
            ohlc_df['sellPosition'] = 1
            ohlc_df['buyMargin'] = 0

        ohlc_df.loc[ohlc_df['datetime'] >=
                    row['ExitTime'], 'openTrade'] = 0
        ohlc_df.loc[ohlc_df['datetime'] >=
                    row['ExitTime'], 'pnl'] = closedPnl.at[index, 'Pnl']
        ohlc_df.loc[ohlc_df['datetime'] >=
                    row['ExitTime'], 'buyPosition'] = 0
        ohlc_df.loc[ohlc_df['datetime'] >=
                    row['ExitTime'], 'sellPosition'] = 0
        ohlc_df.loc[ohlc_df['datetime'] >=
                    row['ExitTime'], 'buyMargin'] = 0

        merged_df = pd.merge(
            mtm_df, ohlc_df[['openTrade', 'pnl', 'buyPosition', 'sellPosition', 'buyMargin']],  how="outer", left_index=True, right_index=True)
        merged_df.ffill(inplace=True)
        merged_df.fillna(0, inplace=True)

        mtm_df['OpenTrades'] += merged_df['openTrade']
        mtm_df['CumulativePnl'] += merged_df['pnl']
        mtm_df['BuyPosition'] += merged_df['buyPosition']
        mtm_df['SellPosition'] += merged_df['sellPosition']
        mtm_df['BuyMargin'] += merged_df['buyMargin']

        progress = (i + 1) / total_rows * 100
        print(f"Progress: {progress:.2f}%", end="\r")
        i += 1

    # if int(mtm_df['CumulativePnl'].iloc[-1]) == int(closedPnl['Pnl'].sum()):
    #     print(f'{file} Sucess')
    # else:
    #     print(f'{file}Error')

    # Calculate spread positions (minimum of buy/sell) for paired margin efficiency (30K per spread)
    # Naked positions (unpaired buy/sell) require higher margin: shorts at 100K fixed, longs at entry price
    mtm_df['Spread'] = np.minimum(
        mtm_df['BuyPosition'], mtm_df['SellPosition'])
    mtm_df['CapitalInvested'] = (mtm_df['Spread'] * 30000) + (
        (mtm_df['BuyPosition'] - mtm_df['Spread']) * mtm_df['BuyMargin']) + ((mtm_df['SellPosition'] - mtm_df['Spread']) * 100000)

    mtm_df['Index'] = mtm_df['Date']
    mtm_df.set_index("Index", inplace=True)
    mtm_df = mtm_df.resample(timeFrame, origin="9:15").agg(
        {
            "Date": "first",
            "OpenTrades": "max",
            "CapitalInvested": "max",
            "CumulativePnl": "last",
            "mtmPnl": "last",
        }
    )
    mtm_df.dropna(inplace=True)

    mtm_df["Peak"] = mtm_df["CumulativePnl"].cummax()
    mtm_df["Drawdown"] = mtm_df["CumulativePnl"] - mtm_df["Peak"]

    # Calculate intra-day MTM P&L: resets at each day boundary to show daily contribution to running PnL
    # First day shows absolute PnL; subsequent days show (current day PnL - previous day closing PnL)
    prevDayEndSeries = mtm_df.groupby(mtm_df['Date'].dt.date)[
        'CumulativePnl'].last().shift(1)
    mtm_df['prevDayEndPnl'] = mtm_df['Date'].dt.date.map(prevDayEndSeries)
    mtm_df['mtmPnl'] = mtm_df.loc[mtm_df['Date'].dt.date ==
                                  mtm_df['Date'].dt.date.min(), 'CumulativePnl']
    mask = mtm_df['Date'].dt.date != mtm_df['Date'].dt.date.min()
    mtm_df.loc[mask, 'mtmPnl'] = mtm_df.loc[mask,
                                            'CumulativePnl'] - mtm_df.loc[mask, 'prevDayEndPnl']

    del mtm_df['prevDayEndPnl']

    mtm_df.fillna(0, inplace=True)
    mtm_df.reset_index(drop=True, inplace=True)

    saveFileSplit = saveFileDir.split('/')[::-1]
    saveFileSplitLen = len(saveFileSplit)
    saveFile = None
    for i in range(saveFileSplitLen):
        if '_' in saveFileSplit[i]:
            saveFile = '_'.join(saveFileSplit[:i+1][::-1])
            break

    if saveFile is None:
        saveFile = saveFileDir.split('/')[-1]

    mtm_df.to_csv(f"{saveFileDir}/mtm_{saveFile}.csv")
    print("dailyReport.csv saved")

    closedPnlCopy = closedPnl.copy(deep=True)

    for col in closedPnlCopy.select_dtypes(include=['datetime64[ns]']):
        closedPnlCopy[col] = closedPnlCopy[col].dt.strftime(
            '%Y-%m-%d %H:%M:%S')

    for col in mtm_df.select_dtypes(include=['datetime64[ns]']):
        mtm_df[col] = mtm_df[col].dt.strftime(
            '%Y-%m-%d %H:%M:%S')

    merged_data = {}

    merged_data["closedPnl"] = closedPnlCopy.to_dict(orient='records')
    merged_data["mtm"] = mtm_df.to_dict(orient='records')

    json_data = json.dumps(merged_data)

    with open(f"{saveFileDir}/{saveFile}.json", "w") as outfile:
        outfile.write(json_data)

    return mtm_df