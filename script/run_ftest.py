#!/usr/bin/python

import argparse
import os
from unittest import defaultTestLoader
from unittest import TextTestRunner


def run_ftest(start_dir, top_level_dir, pattern):
    loader = defaultTestLoader
    tests = loader.discover(start_dir, pattern, top_level_dir)
    TextTestRunner().run(tests)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delta server ftest",
                                     add_help=False)
    s_help = "Where to find the test file(default: %(default)s)"
    parser.add_argument("-s", "--start_dir", default="ftests", help=s_help)
    t_help = "The top level dir(default: %(default)s)."
    parser.add_argument("-t", "--top_level_dir", default="../", help=t_help)
    p_help = ("Files match the pattern(default: %(default)s) will be loaded "
              "for test.")
    parser.add_argument("-p", "--pattern", default="ftest*.py", help=p_help)
    parser.add_argument("--help", action="help", help="Show this help message")

    args = parser.parse_args()
    tests_folder = os.path.join(args.top_level_dir, args.start_dir)
    if os.path.isdir(tests_folder):
        run_ftest(args.start_dir, args.top_level_dir, args.pattern)
    else:
        print "Invalid test folder:%s." % tests_folder