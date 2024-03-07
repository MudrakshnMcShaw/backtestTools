
import logging


def setup_logger(name, log_file, level=logging.INFO):
    """
    Set up a logger with a specified name, log file, and logging level.

    Parameters:
        name (string): The name of the logger.

        log_file (string): The path to the log file.

        level (int): The logging level (default is logging.INFO).

    Returns:
        logging.Logger: The configured logger object.

    Example:
        logger = setup_logger('my_logger', 'example.log')
        logger.info('This is an information message.')
    """
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logging.basicConfig(level=level, filemode='a', force=True)

    return logger


def createPortfolio(filename, stocksPerProcess=4):
    portfolio = []

    with open(filename, 'r') as file:
        elements = [line.strip() for line in file]

    # Create sublists with four elements each
    t = len(elements)//stocksPerProcess
    l = len(elements)//t
    for i in range(0, t):
        if i < (t-1):
            sublist = elements[i*l:(i*l)+l]
            portfolio.append(sublist)
        else:
            sublist = elements[i*l:len(elements)]
            portfolio.append(sublist)

    logging.info(f"Portfolio created: {portfolio}")

    return portfolio
