#!/usr/bin/env python3

import sys
from cloud189.cli.cli import Commander
from cloud189.cli.utils import set_console_style, print_logo, check_update, error

if __name__ == '__main__':
    set_console_style()
    # check_update()
    commander = Commander()
    commander.login()

    if len(sys.argv) >= 2:
        cmd, arg = (sys.argv[1], '') if len(sys.argv) == 2 else (sys.argv[1], sys.argv[2])
        commander.run_one(cmd, arg)
    else:
        # print_logo()
        while True:
            try:
                commander.run()
            except KeyboardInterrupt:
                pass
            # except Exception as e:
            #     error(e)
