from strategies.rsiDmiIntraday import rsiDmiIntradayStrategy
from strategies.rsiDmiOvernight import rsiDmiOvernightStrategy


def strategySelector(devName, strategyName, version):
    if strategyName == "rsiDmiOvernight":
        return rsiDmiOvernightStrategy(devName, strategyName, version)
    if strategyName == "rsiDmiIntraday":
        return rsiDmiIntradayStrategy(devName, strategyName, version)
    else:
        raise Exception("Strategy Name Mismatch")
