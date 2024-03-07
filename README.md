# Table of Contents

* [algoLogic](#algoLogic)
  * [baseAlgoLogic](#algoLogic.baseAlgoLogic)
    * [\_\_init\_\_](#algoLogic.baseAlgoLogic.__init__)
    * [addColumnsToOpenPnlDf](#algoLogic.baseAlgoLogic.addColumnsToOpenPnlDf)
    * [entryOrder](#algoLogic.baseAlgoLogic.entryOrder)
    * [exitOrder](#algoLogic.baseAlgoLogic.exitOrder)
    * [pnlCalculator](#algoLogic.baseAlgoLogic.pnlCalculator)
    * [combinePnlCsv](#algoLogic.baseAlgoLogic.combinePnlCsv)
  * [optAlgoLogic](#algoLogic.optAlgoLogic)
    * [getCallSym](#algoLogic.optAlgoLogic.getCallSym)
    * [getPutSym](#algoLogic.optAlgoLogic.getPutSym)
  * [optIntraDayAlgoLogic](#algoLogic.optIntraDayAlgoLogic)
  * [optOverNightAlgoLogic](#algoLogic.optOverNightAlgoLogic)
* [expiry](#expiry)
  * [getExpiryData](#expiry.getExpiryData)
* [histData](#histData)
  * [connectToMongo](#histData.connectToMongo)
  * [getFnoHistData](#histData.getFnoHistData)
  * [getFnoBacktestData](#histData.getFnoBacktestData)
  * [getEquityHistData](#histData.getEquityHistData)
  * [getEquityBacktestData](#histData.getEquityBacktestData)
* [util](#util)
  * [setup\_logger](#util.setup_logger)

<a id="algoLogic"></a>

# algoLogic

<a id="algoLogic.baseAlgoLogic"></a>

## baseAlgoLogic Objects

```python
class baseAlgoLogic()
```

The `baseAlgoLogic` class is a foundational class for implementing algorithmic trading logic.
It provides methods for managing trades, calculating profit and loss (PnL), and handling data storage.
This class serves as a base for more specific algorithmic trading strategies.

**Attributes**:

- `conn` _MongoClient_ - Stores a MongoDB connection object. Initially set to None.
  
- `timeData` _float_ - Stores timestamp
  
- `humanTime` _datetime_ - Stores python datetime object
  
- `unrealisedPnl` _int_ - Stores Unrealized Profit and Loss
  
- `realisedPnl` _int_ - Stores Realized Profit and Loss
  
- `netPnl` _int_ - Stores Net Profit and Loss
  
- `openPnl` _DataFrame_ - Dataframe that stores open trades
  
- `closedPnl` _DataFrame_ - Dataframe that stores closed trades
  
- `fileDir` _Dictionary_ - Dictionary containing several file directories for storing files
  
  > backtestResultsStrategyUid - Backtest Results Folder
  
  > backtestResultsOpenPnl: File directory to store openPnl csv
  
  > backtestResultsClosePnl: File directory to store closedPnl csv
  
  > backtestResultsCandleData: File directory to store OHLC Data csv
  
  > backtestResultsStrategyLogs: File directory to store strategy logs

<a id="algoLogic.baseAlgoLogic.__init__"></a>

#### \_\_init\_\_

```python
def __init__(devName, strategyName, version)
```

This method initializes an instance of the `baseAlgoLogic` class.

**Arguments**:

- `devName` _string_ - Developer Name
- `strategyName` _string_ - Strategy Name
- `version` _string_ - Version Name

<a id="algoLogic.baseAlgoLogic.addColumnsToOpenPnlDf"></a>

#### addColumnsToOpenPnlDf

```python
def addColumnsToOpenPnlDf(columns)
```

Creates multiple new column in openPnl Dataframe

**Arguments**:

- `columns` _list_ - List of column names(string) to be added.

<a id="algoLogic.baseAlgoLogic.entryOrder"></a>

#### entryOrder

```python
def entryOrder(entryPrice,
               symbol,
               quantity,
               positionStatus,
               extraColDict=None)
```

Executes an entry order for a trade and adds it to the `openPnl` DataFrame.

**Arguments**:

- `entryPrice` _float_ - List of column names(string) to be added.
  
- `symbol` _string_ - Symbol of the asset being traded.
  
- `quantity` _int_ - Quantity of the asset being traded.
  
- `positionStatus` _string_ - Position status, either "BUY" or "SELL".
  
- `extraColDict` _Dictionary, optional_ - Additional columns to be included in the trade entry.

<a id="algoLogic.baseAlgoLogic.exitOrder"></a>

#### exitOrder

```python
def exitOrder(index, exitType, exitPrice=None)
```

Executes an exit order for a trade and moves it from the `openPnl` DataFrame to the `closedPnl` DataFrame.

**Arguments**:

- `index` _int_ - Index of the trade in the `openPnl` DataFrame.
  
- `exitType` _string_ - Type of exit order.
  
- `exitPrice` _float, optional_ - Exit price of the trade.

<a id="algoLogic.baseAlgoLogic.pnlCalculator"></a>

#### pnlCalculator

```python
def pnlCalculator()
```

Calculates the profit and loss (PnL) for both open and closed trades.

<a id="algoLogic.baseAlgoLogic.combinePnlCsv"></a>

#### combinePnlCsv

```python
def combinePnlCsv()
```

Combines and saves the data of open and closed trades to CSV files.

**Returns**:

- `openPnl` _DataFrame_ - Combined DataFrame of open trades.
  
- `closedPnl` _DataFrame_ - Combined DataFrame of closed trades.

<a id="algoLogic.optAlgoLogic"></a>

## optAlgoLogic Objects

```python
class optAlgoLogic(baseAlgoLogic)
```

Options Algo Logic Class
Inherits from baseAlgoLogic class.

**Attributes**:

  Inherits all attributes and functions from the baseAlgoLogic class.

<a id="algoLogic.optAlgoLogic.getCallSym"></a>

#### getCallSym

```python
def getCallSym(date, baseSym, indexPrice, otmFactor=0)
```

Creates the call symbol based on provided parameters.

**Arguments**:

- `date` _datetime or float_ - Date at which the expiry date needs to be decided.
  
- `baseSym` _string_ - Base symbol for the option.
  
- `indexPrice` _float_ - Current price of the baseSym.
  
- `otmFactor` _int, optional_ - Factor for calculating the strike price. Default is 0.
  

**Returns**:

- `callSym` _string_ - Call symbol generated based on the parameters.

<a id="algoLogic.optAlgoLogic.getPutSym"></a>

#### getPutSym

```python
def getPutSym(date, baseSym, indexPrice, otmFactor=0)
```

Creates the put symbol based on provided parameters.

**Arguments**:

- `date` _datetime or float_ - Date at which the expiry date needs to be decided.
  
- `baseSym` _string_ - Base symbol for the option.
  
- `indexPrice` _float_ - Current price of the baseSym.
  
- `otmFactor` _int, optional_ - Factor for calculating the strike price. Default is 0.
  

**Returns**:

- `putSym` _string_ - Put symbol generated based on the parameters.

<a id="algoLogic.optIntraDayAlgoLogic"></a>

## optIntraDayAlgoLogic Objects

```python
class optIntraDayAlgoLogic(optAlgoLogic)
```

Options Intraday Algo Logic Class
Inherits from optAlgoLogic class.

**Attributes**:

  Inherits all attributes and functions from the optAlgoLogic class.

<a id="algoLogic.optOverNightAlgoLogic"></a>

## optOverNightAlgoLogic Objects

```python
class optOverNightAlgoLogic(optAlgoLogic)
```

Options Overnight Algo Logic Class
Inherits from optAlgoLogic class.

**Attributes**:

  Inherits all attributes and functions from the optAlgoLogic class.

<a id="expiry"></a>

# expiry

<a id="expiry.getExpiryData"></a>

#### getExpiryData

```python
def getExpiryData(date, sym)
```

Retrieves expiry data for a given date and symbol from MongoDB collections.

**Arguments**:

- `date` _datetime or float_ - The date for which expiry data is requested. It can be either a datetime object or a timestamp in float format.
  
- `sym` _string_ - The base symbol for which expiry data is requested.
  

**Returns**:

- `dictionary` - A dictionary containing expiry data if found, otherwise None.

<a id="histData"></a>

# histData

<a id="histData.connectToMongo"></a>

#### connectToMongo

```python
def connectToMongo()
```

Connects to MongoDB database.

**Returns**:

- `MongoClient` - A MongoDB client object representing the connection.

<a id="histData.getFnoHistData"></a>

#### getFnoHistData

```python
def getFnoHistData(symbol, timestamp)
```

Retrieves historical data for a given Fno symbol or Indices symbol and timestamp from MongoDB collection.

**Arguments**:

- `symbol` _string_ - The symbol for which historical data is requested.
  
- `timestamp` _float_ - The timestamp for which historical data is requested.
  

**Returns**:

- `dict` - A dictionary containing historical data if found, otherwise None.

<a id="histData.getFnoBacktestData"></a>

#### getFnoBacktestData

```python
def getFnoBacktestData(symbol, startDateTime, endDateTime, interval)
```

Retrieves backtest data i.e. range of data for a given Fno symbol or Indices symbol, start and end datetime, and interval.

**Arguments**:

- `symbol` _string_ - The symbol for which backtest data is requested.
  
- `startDateTime` _float or datetime_ - The start datetime for the backtest data.
  
- `endDateTime` _float or datetime_ - The end datetime for the backtest data.
  
- `interval` _string_ - The resampling interval for the data.
  

**Returns**:

- `DataFrame` - A pandas DataFrame containing resampled backtest data.

<a id="histData.getEquityHistData"></a>

#### getEquityHistData

```python
def getEquityHistData(symbol, timestamp)
```

Retrieves historical data for a given equity symbol and timestamp from MongoDB collection.

**Arguments**:

- `symbol` _string_ - The symbol for which historical data is requested.
  
- `timestamp` _float_ - The timestamp for which historical data is requested.
  

**Returns**:

- `dict` - A dictionary containing historical data if found, otherwise None.

<a id="histData.getEquityBacktestData"></a>

#### getEquityBacktestData

```python
def getEquityBacktestData(symbol, startDateTime, endDateTime)
```

Retrieves backtest data i.e. range of data for a given equity symbol, start and end datetime, and interval.

**Arguments**:

- `symbol` _string_ - The symbol for which backtest data is requested.
  
- `startDateTime` _float or datetime_ - The start datetime for the backtest data.
  
- `endDateTime` _float or datetime_ - The end datetime for the backtest data.
  
- `interval` _string_ - The resampling interval for the data.
  

**Returns**:

- `DataFrame` - A pandas DataFrame containing resampled backtest data.

<a id="util"></a>

# util

<a id="util.setup_logger"></a>

#### setup\_logger

```python
def setup_logger(name, log_file, level=logging.INFO)
```

Set up a logger with a specified name, log file, and logging level.

**Arguments**:

- `name` _string_ - The name of the logger.
  
- `log_file` _string_ - The path to the log file.
  
- `level` _int_ - The logging level (default is logging.INFO).
  

**Returns**:

- `logging.Logger` - The configured logger object.
  

**Example**:

  logger = setup_logger('my_logger', 'example.log')
  logger.info('This is an information message.')

