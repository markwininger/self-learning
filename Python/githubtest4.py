#!/usr/local/bin python3.6

try:
    import logging
    import sys
    import pandas
except ImportError:
    print(f"{sys.exc_info()}")


"""
It takes a list of lists and converts it to a pandas dataframe.

:param table_info: a list of lists, where each list is a row in the table
:param output_file: The name of the file to write the output to
:param sortby: the column to sort by
:param ascending: True or False
"""


def do_pandas(table_info, output_file="", sortby=None, ascending=None):
    pandas.set_option("max_columns", None)
    if sortby != None:
        table_tmp = pandas.DataFrame(data=table_info)
        table = table_tmp.sort_values(by=sortby, ascending=ascending)
    else:
        table = pandas.DataFrame(data=table_info)
    print(table)
    if output_file != "":
        with open(output_file, "a") as outfile:
            table.to_csv(outfile, index=False, header=outfile.tell() == 0)
