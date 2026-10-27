"""Parse user CSVs without exposing content in UI exception messages."""
import pandas as pd


class CSVInputError(ValueError):
    pass


def read_csv_input(source):
    try:
        frame = pd.read_csv(source)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError, OSError):
        raise CSVInputError('CSV无法读取；请使用含表头和数据行的有效UTF-8 CSV文件。') from None
    if frame.empty:
        raise CSVInputError('CSV没有数据行；请补充数据后重新上传。')
    return frame
