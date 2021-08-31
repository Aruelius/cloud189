#!/usr/bin/env python3
# -*- coding=utf-8 -*-

import sys
from cloud189.cli.cli import Commander
from cloud189.cli.utils import print_logo, check_update, error

if __name__ == '__main__':
    commander = Commander()
    commander.login(("--auto", ))

    if len(sys.argv) >= 2:
        cmd, args = (sys.argv[1], []) if len(sys.argv) == 2 else (sys.argv[1], [*sys.argv[2:]])
        commander.run_one(cmd, args)
    else:
        check_update()
        print_logo()
        while True:
            try:
                commander.run()
            except KeyboardInterrupt:
                pass
            except Exception as e:
                error(e)
