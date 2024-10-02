#!/usr/bin/env python

import argparse
import sys

from qsm_ci import run, eval, upload, parse_bids

def main():

    # create parser
    parser = argparse.ArgumentParser(description='QSM-CI')
    parser.add_argument(
        'task',
        type=str,
        choices=['run', 'eval', 'upload', 'parse'],
        help='Choose between running the QSM algorithm, evaluating the results, or uploading the results to Nectar Swift Object Storage'
    )

    # parse args
    args, unknown = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + unknown

    # run the task
    if args.task == 'run':
        run.main()
        
    if args.task == 'eval':
        eval.main()

    if args.task == 'upload':
        upload.main()

    if args.task == 'parse':
        parse_bids.main()


if __name__ == '__main__':
    main()

