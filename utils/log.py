import logging, inspect

logger_is_setup = False
def setup_logger():
    """
    Setup logger for Delta.
    """
    global logger_is_setup
    if logger_is_setup:
        return True

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    default_handler = logging.StreamHandler()
    default_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(default_handler)
    logging.root = logger
    logger_is_setup = True
    return True

def get_logger():
    if not logger_is_setup:
        setup_logger()
    return logging.root


def log(level, message, *args, **kwargs):
    frame,filename,line_number,function_name,lines,index = inspect.stack()[2]
    logger = get_logger()
    message = '[%s: %s] %s' % (filename, line_number, message)

    logger.log(level, *((message,)+args), **kwargs)

def debug(message, *args, **kw):
    """
    Log a message with severity 'DEBUG' on the logger.
    """
    log(logging.DEBUG, message, *args, **kw)

def info(message, *args, **kw):
    """
    Log a message with severity 'INFO' on the logger.
    """
    log(logging.INFO, message, *args, **kw)

msg = info

def warning(message, *args, **kw):
    """
    Log a message with severity 'WARNING' on the logger.
    """
    log(logging.WARNING, message, *args, **kw)

warn = warning

def error(message, *args, **kw):
    log(logging.ERROR, message, *args, **kw)

err = error

def critical(message, *args, **kw):
    log(logging.CRITICAL, message, *args, **kw)





    #=====================

def start_logging(level=logging.DEBUG):
    logger = logging.getLogger()
    logger.setLevel(level)

    frame,filename,line_number,function_name,lines,index = inspect.stack()[1]

    formatter = logging.Formatter("%%(asctime)s [%%(levelname)s] [%(pathname)s:%(lineno)s] %%(message)s" % \
                                  {'pathname': filename, 'lineno': line_number}
    )
    default_handler = logging.StreamHandler()
    default_handler.setFormatter(formatter)
    logger.addHandler(default_handler)
    #logger.info('Start logging on :%s' % filename)
    return logger