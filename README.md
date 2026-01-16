# BacktestTools

A comprehensive Python framework for backtesting algorithmic trading strategies on Indian equity and derivatives markets. Built for rapid strategy prototyping and performance analysis with support for both options (F&O) and equity instruments.

## Overview

**backtestTools** is an enterprise-grade backtesting framework designed to:
- Simulate trading strategies on historical market data
- Support multiple trading styles: intraday and overnight strategies
- Handle both equity and derivatives (options/futures) trading
- Provide detailed P&L calculations and performance metrics
- Integrate with MongoDB for historical OHLC data storage
- Generate comprehensive daily and cumulative performance reports

### Key Features

- **Multi-Strategy Support**: Options (F&O) and equity trading with intraday/overnight variants
- **MongoDB Integration**: Efficient data retrieval from centralized historical database
- **Advanced P&L Tracking**: Real-time and realized P&L calculations with MTM support
- **Performance Analytics**: Daily reports, drawdown analysis, capital utilization metrics
- **Caching Mechanisms**: Optimized data retrieval with symbol-level and expiry-level caching
- **Flexible Architecture**: Easily extensible base classes for custom strategy development

## Table of Contents

* [Installation](#installation)
* [Project Structure](#project-structure)
* [Core Modules](#core-modules)
  * [algoLogic](#algoLogic) - Trading Algorithm Base Classes
  * [histData](#histData) - Historical Data Management
  * [expiry](#expiry) - Options Expiry Management
  * [util](#util) - Utility Functions
* [Usage Examples](#usage-examples)
* [API Reference](#api-reference)

## Installation

```bash
pip install -e .
```

### Dependencies

- pandas: Data manipulation and time series analysis
- numpy: Numerical computations
- pymongo: MongoDB connectivity for historical data
- talib: Technical analysis indicators
- termcolor: Colored terminal output

## Project Structure

```
backtestTools/
├── backtestTools/          # Core framework modules
│   ├── algoLogic.py       # Trading algorithm base classes
│   ├── histData.py        # Historical data retrieval
│   ├── expiry.py          # Options expiry management
│   └── util.py            # Utility functions
├── examples/              # Example strategies
│   ├── optEmaOvernight.py # Options overnight EMA strategy
│   ├── rdx.py             # Options overnight RDX strategy
│   ├── straddle.py        # Options intraday straddle strategy
│   └── Equity/
│       ├── executionLogic.py      # Equity strategy execution
│       ├── strategy.py             # Strategy selector
│       └── strategies/
│           ├── rsiDmiIntraday.py   # Equity intraday RSI+DMI
│           └── rsiDmiOvernight.py  # Equity overnight RSI+DMI
└── README.md
```

## Core Modules

<a id="algoLogic"></a>

### algoLogic - Algorithm Logic Module

Provides foundational classes for implementing algorithmic trading strategies with trade management and P&L tracking.

#### Class Hierarchy

```
baseAlgoLogic (Base class for all strategies)
├── optAlgoLogic (Options trading with expiry/strike management)
│   ├── optIntraDayAlgoLogic (Single-day options strategies)
│   └── optOverNightAlgoLogic (Multi-day options strategies)
└── equityAlgoLogic
    ├── equityIntradayAlgoLogic (Single-day equity strategies)
    └── equityOverNightAlgoLogic (Multi-day equity strategies)
```

#### Core Components

<a id="algoLogic.baseAlgoLogic"></a>

### baseAlgoLogic

```python
class baseAlgoLogic()
```

The foundational class for all trading algorithms. Manages trade execution, P&L calculations, and data persistence.

**Key Attributes**:

- `openPnl` _DataFrame_ - Active trades with entry price, quantity, and unrealized P&L
- `closedPnl` _DataFrame_ - Closed trades with entry/exit prices and realized P&L
- `unrealisedPnl` _int_ - Unrealized Profit and Loss from open trades
- `realisedPnl` _int_ - Realized Profit and Loss from closed trades
- `netPnl` _int_ - Total P&L (realized + unrealized)
- `strategyLogger` _logging.Logger_ - Strategy execution logs

**Key Methods**:

<a id="algoLogic.baseAlgoLogic.__init__"></a>

#### \_\_init\_\_

```python
def __init__(self, devName, strategyName, version)
```

Initializes the algorithm with strategy metadata and creates result directories.

**Arguments**:
- `devName` _string_ - Developer identifier
- `strategyName` _string_ - Name of the trading strategy
- `version` _string_ - Strategy version identifier

<a id="algoLogic.baseAlgoLogic.addColumnsToOpenPnlDf"></a>

#### addColumnsToOpenPnlDf

```python
def addColumnsToOpenPnlDf(columns)
```

Dynamically add new columns to the open P&L tracking DataFrame.

**Arguments**:
- `columns` _list_ - Column names to add

<a id="algoLogic.baseAlgoLogic.entryOrder"></a>

#### entryOrder

```python
def entryOrder(entryPrice, symbol, quantity, positionStatus, extraColDict=None)
```

Record a trade entry with position details.

**Arguments**:
- `entryPrice` _float_ - Entry price of the position
- `symbol` _string_ - Trading symbol
- `quantity` _int_ - Position size
- `positionStatus` _string_ - "BUY" or "SELL"
- `extraColDict` _dict, optional_ - Additional custom columns

<a id="algoLogic.baseAlgoLogic.exitOrder"></a>

#### exitOrder

```python
def exitOrder(index, exitType, exitPrice=None)
```

Close a position and move from open to closed trades.

**Arguments**:
- `index` _int_ - Index of trade in openPnl DataFrame
- `exitType` _string_ - Type of exit (e.g., "stoploss", "target", "manual")
- `exitPrice` _float, optional_ - Exit price of the position

<a id="algoLogic.baseAlgoLogic.pnlCalculator"></a>

#### pnlCalculator

```python
def pnlCalculator()
```

Calculate P&L for all open and closed positions.

<a id="algoLogic.baseAlgoLogic.combinePnlCsv"></a>

#### combinePnlCsv

```python
def combinePnlCsv()
```

Persist open and closed trades to CSV files.

**Returns**:
- `openPnl` _DataFrame_ - Open trades
- `closedPnl` _DataFrame_ - Closed trades

<a id="algoLogic.optAlgoLogic"></a>

### optAlgoLogic

```python
class optAlgoLogic(baseAlgoLogic)
```

Options-specific trading logic with dynamic strike calculation, expiry management, and intelligent caching.

**Key Attributes**:
- `symbolDataCache` _dict_ - In-memory cache for F&O symbol data
- `expiryDataCache` _dict_ - In-memory cache for option expiry information

**Key Methods**:

<a id="algoLogic.optAlgoLogic.getCallSym"></a>

#### getCallSym

```python
def getCallSym(date, baseSym, indexPrice, expiry=None, otmFactor=0, strikeDist=None, conn=None)
```

Generate a call option symbol with strike based on current price.

**Arguments**:
- `date` _datetime or float_ - Reference date for expiry determination
- `baseSym` _string_ - Base symbol (e.g., "NIFTY", "BANKNIFTY")
- `indexPrice` _float_ - Current underlying price
- `expiry` _string, optional_ - Specific expiry date (e.g., "27MAR25")
- `otmFactor` _int, optional_ - Out-of-money factor for strike offset
- `strikeDist` _int, optional_ - Strike distance (default: auto-determined)
- `conn` _MongoClient, optional_ - MongoDB connection for data lookup

**Returns**:
- `callSym` _string_ - Generated call option symbol

<a id="algoLogic.optAlgoLogic.getPutSym"></a>

#### getPutSym

```python
def getPutSym(date, baseSym, indexPrice, expiry=None, otmFactor=0, strikeDist=None, conn=None)
```

Generate a put option symbol with strike based on current price.

**Arguments** (same as getCallSym):
- See getCallSym

**Returns**:
- `putSym` _string_ - Generated put option symbol

<a id="algoLogic.optAlgoLogic.fetchAndCacheFnoHistData"></a>

#### fetchAndCacheFnoHistData

```python
def fetchAndCacheFnoHistData(symbol, timestamp, maxCacheSize=100, conn=None)
```

Fetch and cache F&O historical data with automatic eviction of expired contracts.

**Arguments**:
- `symbol` _string_ - F&O symbol
- `timestamp` _float_ - Timestamp for data request
- `maxCacheSize` _int, optional_ - Maximum cache entries (default: 100)
- `conn` _MongoClient, optional_ - MongoDB connection for data retrieval

**Returns**:
- `DataFrame` - Historical OHLC data for the requested symbol and timestamp

<a id="algoLogic.optAlgoLogic.fetchAndCacheExpiryData"></a>

#### fetchAndCacheExpiryData

```python
def fetchAndCacheExpiryData(date, sym, conn=None)
```

Fetch and cache option expiry information from MongoDB.

**Arguments**:
- `date` _datetime or float_ - Reference date for expiry lookup
- `sym` _string_ - Base symbol (e.g., "NIFTY", "BANKNIFTY")
- `conn` _MongoClient, optional_ - MongoDB connection for data retrieval

**Returns**:
- `dict` - Expiry data including CurrentExpiry and StrikeDist if found, otherwise None

<a id="algoLogic.optIntraDayAlgoLogic"></a>

### optIntraDayAlgoLogic

```python
class optIntraDayAlgoLogic(optAlgoLogic)
```

Options trading for single-day intraday strategies. Inherits all methods from optAlgoLogic with optional CSV persistence.

**Key Methods**:

#### entryOrder

```python
def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None, saveCsv=False)
```

Record an intraday options entry order with optional CSV persistence.

**Arguments**:
- `entryPrice` _float_ - Entry price of the option
- `symbol` _string_ - Option symbol
- `quantity` _int_ - Position size
- `positionStatus` _string_ - "BUY" or "SELL"
- `extraColDict` _dict, optional_ - Additional custom columns
- `saveCsv` _bool, optional_ - Save openPnl to CSV (default: False)

#### exitOrder

```python
def exitOrder(self, index, exitType, exitPrice=None)
```

Close an intraday options position and save to CSV.

**Arguments**:
- `index` _int_ - Index of trade in openPnl DataFrame
- `exitType` _string_ - Type of exit
- `exitPrice` _float, optional_ - Exit price of the option

<a id="algoLogic.optOverNightAlgoLogic"></a>

### optOverNightAlgoLogic

```python
class optOverNightAlgoLogic(optAlgoLogic)
```

Options trading for multi-day overnight strategies. Inherits all methods from optAlgoLogic with persistent CSV storage.

**Key Methods**:

#### entryOrder

```python
def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None, saveCsv=False)
```

Record an overnight options entry order with optional persistent CSV storage.

**Arguments**:
- `entryPrice` _float_ - Entry price of the option
- `symbol` _string_ - Option symbol
- `quantity` _int_ - Position size
- `positionStatus` _string_ - "BUY" or "SELL"
- `extraColDict` _dict, optional_ - Additional custom columns
- `saveCsv` _bool, optional_ - Save openPnl to persistent CSV (default: False)

#### exitOrder

```python
def exitOrder(self, index, exitType, exitPrice=None)
```

Close an overnight options position and save to persistent CSV.

**Arguments**:
- `index` _int_ - Index of trade in openPnl DataFrame
- `exitType` _string_ - Type of exit
- `exitPrice` _float, optional_ - Exit price of the option

<a id="algoLogic.equityOverNightAlgoLogic"></a>

### equityOverNightAlgoLogic

```python
class equityOverNightAlgoLogic(baseAlgoLogic)
```

Equity trading for overnight strategies with persistent position tracking across multiple days.

**Key Attributes**:
- Uses non-dated filenames for persistent multi-day tracking
- Maintains separate logger for each stock

**Key Methods**:

<a id="algoLogic.equityOverNightAlgoLogic.__init__"></a>

#### \_\_init\_\_

```python
def __init__(self, stockName, fileDir)
```

Initialize overnight equity logic with persistent CSV storage.

**Arguments**:
- `stockName` _string_ - Equity symbol
- `fileDir` _dict_ - File directories for results storage

<a id="algoLogic.equityOverNightAlgoLogic.entryOrder"></a>

#### entryOrder

```python
def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None, saveCsv=False)
```

Record an overnight equity entry order with optional persistent CSV storage.

**Arguments**:
- `entryPrice` _float_ - Entry price of the equity
- `symbol` _string_ - Stock ticker symbol
- `quantity` _int_ - Number of shares
- `positionStatus` _string_ - "BUY" or "SELL"
- `extraColDict` _dict, optional_ - Additional custom columns
- `saveCsv` _bool, optional_ - Save openPnl to persistent CSV file (default: False)

<a id="algoLogic.equityOverNightAlgoLogic.exitOrder"></a>

#### exitOrder

```python
def exitOrder(self, index, exitType, exitPrice=None)
```

Close an overnight equity position and save to persistent CSV.

**Arguments**:
- `index` _int_ - Index of trade in openPnl DataFrame
- `exitType` _string_ - Type of exit (e.g., "stoploss", "target", "manual")
- `exitPrice` _float, optional_ - Exit price of the equity

<a id="algoLogic.equityIntradayAlgoLogic"></a>

### equityIntradayAlgoLogic

```python
class equityIntradayAlgoLogic(baseAlgoLogic)
```

Equity trading for intraday strategies with daily position snapshots and logger refresh per trading day.

**Key Attributes**:
- Saves open/closed positions with date in filename for daily tracking
- Logger includes date and is refreshed for new trading sessions

**Key Methods**:

<a id="algoLogic.equityIntradayAlgoLogic.__init__"></a>

#### \_\_init\_\_

```python
def __init__(self, stockName, fileDir)
```

Initialize intraday equity logic with daily CSV snapshots.

**Arguments**:
- `stockName` _string_ - Equity symbol
- `fileDir` _dict_ - File directories for results storage

<a id="algoLogic.equityIntradayAlgoLogic.init_logger"></a>

#### init_logger

```python
def init_logger(self)
```

Reinitialize logger for new trading day with current date in filename.

**Returns**:
- `None`

<a id="algoLogic.equityIntradayAlgoLogic.entryOrder"></a>

#### entryOrder

```python
def entryOrder(self, entryPrice, symbol, quantity, positionStatus, extraColDict=None, saveCsv=False)
```

Record an intraday equity entry order with optional daily CSV persistence.

**Arguments**:
- `entryPrice` _float_ - Entry price of the equity
- `symbol` _string_ - Stock ticker symbol
- `quantity` _int_ - Number of shares
- `positionStatus` _string_ - "BUY" or "SELL"
- `extraColDict` _dict, optional_ - Additional custom columns
- `saveCsv` _bool, optional_ - Save openPnl to daily-dated CSV (default: False)

<a id="algoLogic.equityIntradayAlgoLogic.exitOrder"></a>

#### exitOrder

```python
def exitOrder(self, index, exitType, exitPrice=None)
```

Close an intraday equity position and save to daily-dated CSV.

**Arguments**:
- `index` _int_ - Index of trade in openPnl DataFrame
- `exitType` _string_ - Type of exit (e.g., "stoploss", "target", "manual")
- `exitPrice` _float, optional_ - Exit price of the equity

<a id="histData"></a>

## histData - Historical Data Module

Manages data retrieval from MongoDB for both F&O and equity instruments.

<a id="histData.connectToMongo"></a>

#### connectToMongo

```python
def connectToMongo()
```

Establish MongoDB connection for data retrieval.

**Returns**:
- `MongoClient` - Connected MongoDB client

<a id="histData.getFnoHistData"></a>

#### getFnoHistData

```python
def getFnoHistData(symbol, timestamp, conn=None)
```

Retrieve single tick of F&O (Futures/Options) OHLC data.

**Arguments**:
- `symbol` _string_ - F&O symbol
- `timestamp` _float_ - Epoch timestamp
- `conn` _MongoClient, optional_ - Existing connection

**Returns**:
- `dict` - OHLC data point or None

<a id="histData.getFnoBacktestData"></a>

#### getFnoBacktestData

```python
def getFnoBacktestData(symbol, startDateTime, endDateTime, interval, conn=None)
```

Retrieve and resample F&O data range for backtesting.

**Arguments**:
- `symbol` _string_ - F&O symbol
- `startDateTime` _float or datetime_ - Start timestamp
- `endDateTime` _float or datetime_ - End timestamp
- `interval` _string_ - Resampling interval (e.g., "1Min", "5Min", "1D")
- `conn` _MongoClient, optional_ - Existing connection

**Returns**:
- `DataFrame` - Resampled OHLC data

<a id="histData.getEquityHistData"></a>

#### getEquityHistData

```python
def getEquityHistData(symbol, timestamp, conn=None)
```

Retrieve single tick of equity 1-minute OHLC data.

**Arguments**:
- `symbol` _string_ - Equity symbol
- `timestamp` _float_ - Epoch timestamp
- `conn` _MongoClient, optional_ - Existing connection

**Returns**:
- `dict` - OHLC data point or None

<a id="histData.getEquityBacktestData"></a>

#### getEquityBacktestData

```python
def getEquityBacktestData(symbol, startDateTime, endDateTime, interval, conn=None)
```

Retrieve and resample equity data range for backtesting.

**Arguments**:
- `symbol` _string_ - Equity symbol
- `startDateTime` _float or datetime_ - Start timestamp
- `endDateTime` _float or datetime_ - End timestamp
- `interval` _string_ - Resampling interval (e.g., "1Min", "5Min", "1D")
- `conn` _MongoClient, optional_ - Existing connection

**Returns**:
- `DataFrame` - Resampled OHLC data

<a id="expiry"></a>

## expiry - Options Expiry Module

<a id="expiry.getExpiryData"></a>

#### getExpiryData

```python
def getExpiryData(date, sym, conn=None)
```

Retrieve option expiry data for a given date and symbol from MongoDB.

**Arguments**:
- `date` _datetime or float_ - Reference date for expiry lookup (can be datetime object or epoch timestamp)
- `sym` _string_ - Base symbol (e.g., "NIFTY", "BANKNIFTY")
- `conn` _MongoClient, optional_ - MongoDB connection object (default: None, creates new connection if needed)

**Returns**:
- `dict` - Dictionary containing expiry information (CurrentExpiry, StrikeDist) if found, otherwise None

<a id="util"></a>

## util - Utility Functions Module

Comprehensive utility functions for strategy development, reporting, and analysis.

<a id="util.setup_logger"></a>

#### setup_logger

```python
def setup_logger(name, log_file, level=logging.INFO, formatter=logging.Formatter("%(message)s"))
```

Configure a logger for strategy execution.

**Arguments**:
- `name` _string_ - Logger identifier
- `log_file` _string_ - Output log file path
- `level` _int_ - Logging level (default: INFO)
- `formatter` _logging.Formatter_ - Message format

**Returns**:
- `logging.Logger` - Configured logger

**Example**:
```python
logger = setup_logger('strategy_logger', 'backtest.log')
logger.info('Trade executed at 100.50')
```

<a id="util.createPortfolio"></a>

#### createPortfolio

```python
def createPortfolio(filename, stocksPerProcess=4)
```

Create batched portfolio from newline-separated symbol file.

**Arguments**:
- `filename` _string_ - Path to file with stock symbols (one per line)
- `stocksPerProcess` _int_ - Symbols per batch (default: 4)

**Returns**:
- `list` - List of symbol batches for parallel processing

**Example**:
```python
portfolio = createPortfolio('stocks.txt', stocksPerProcess=5)
# Returns: [['RELIANCE', 'INFY', 'TCS', 'WIPRO', 'LT'], ['MARUTI', ...]]
```

<a id="util.calculateDailyReport"></a>

#### calculateDailyReport

```python
def calculateDailyReport(closedPnl, saveFileDir, timeFrame=timedelta(minutes=1), mtm=False, fno=True)
```

Generate daily performance report with time-aggregated metrics.

**Arguments**:
- `closedPnl` _DataFrame_ - Closed trades from strategy
- `saveFileDir` _string_ - Directory for report output
- `timeFrame` _timedelta_ - Aggregation period (default: 1 minute)
- `mtm` _bool_ - Include mark-to-market calculations (default: False)
- `fno` _bool_ - F&O vs equity data source (default: True for F&O)

**Returns**:
- `DataFrame` - Daily report with P&L metrics

<a id="util.limitCapital"></a>

#### limitCapital

```python
def limitCapital(originalClosedPnl, saveFileDir, maxCapitalAmount)
```

Apply capital constraints to trades beyond specified limit.

**Arguments**:
- `originalClosedPnl` _DataFrame_ - Original closed trades
- `saveFileDir` _string_ - Output directory
- `maxCapitalAmount` _float_ - Maximum capital allowed

**Returns**:
- `DataFrame` - Modified closed trades respecting capital limit

<a id="util.generateReportFile"></a>

#### generateReportFile

```python
def generateReportFile(dailyReport, saveFileDir)
```

Generate human-readable performance summary report.

**Arguments**:
- `dailyReport` _DataFrame_ - Daily report from calculateDailyReport
- `saveFileDir` _string_ - Output directory for report

**Returns**:
- `max_drawdown_percentage` _float_ - Maximum drawdown %

<a id="util.calculate_mtm"></a>

#### calculate_mtm

```python
def calculate_mtm(closedPnl, saveFileDir, timeFrame="15T", mtm=False, equityMarket=True, conn=None)
```

Calculate minute-by-minute mark-to-market positions and P&L with resampled reporting.

Builds a detailed time-series of portfolio metrics by iterating through each trade and computing its contribution to open positions, capital required, and mark-to-market P&L at each minute. Results are resampled to specified timeframe and aggregated with position tracking and margin calculations.

**Arguments**:
- `closedPnl` _DataFrame_ - Trade records with columns: Key (entry datetime), ExitTime (exit datetime), Symbol, EntryPrice, Quantity, PositionStatus (1 for BUY, -1 for SELL), Pnl (realized P&L)
- `saveFileDir` _string_ - Directory where output files will be saved (creates: mtm_{name}.csv and {name}.json)
- `timeFrame` _string, optional_ - Resampling frequency for aggregated output (default: "15T" for 15-minute bars; other values: "1H", "1D", "1min")
- `mtm` _bool, optional_ - Legacy parameter for backward compatibility (default: False)
- `equityMarket` _bool, optional_ - If True, retrieves equity price data using getEquityBacktestData; if False, retrieves F&O price data using getFnoBacktestData (default: True)
- `conn` _MongoClient, optional_ - MongoDB connection object for efficiency in batch processing (default: None)

**Returns**:
- `DataFrame` - Resampled MTM report with columns:
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
