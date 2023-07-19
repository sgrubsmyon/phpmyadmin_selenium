#!/usr/bin/env python3
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
####################################################################################
#
# A Python script to automate the download of SQL dump backups
# via a phpMyAdmin web interface.
#
# tested on Python 3.10
# requires: selenium (https://www.selenium.dev/)
#
# Markus Voge, started 2023-07

import argparse
import os
import sys

from selenium import webdriver
from selenium.webdriver.common.by import By

DEFAULT_PREFIX_FORMAT = r'%Y-%m-%d--%H-%M-%S-UTC_'


def download_mysql_backup(url, user, password, dry_run=False, overwrite_existing=False, prepend_date=True, basename=None,
                          output_directory=os.getcwd(), exclude_dbs=None, compression="none", prefix_format=None,
                          timeout=60, http_auth=None, server_name=None, **kwargs):
    prefix_format = prefix_format or DEFAULT_PREFIX_FORMAT
    exclude_dbs = exclude_dbs.split(',') or []
    encoding = '' if compression == 'gzip' else 'gzip'

    driver = webdriver.Chrome()
    driver.get(url)
    print(driver)


download_mysql_backup()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="phpmyadmin_backup_down",
        description="Automated download of MySQL backup files from a phpMyAdmin "
                    "web interface, using just one command on the commandline.",
        epilog="Written by Markus Voge, because https://github.com/qubitstream/phpmyadmin_sql_backup "
               "is defunct (actually its dependency grab is unmaintained and not working anymore "
               "since Python 3.10)."
    )

    parser.add_argument('url', metavar='URL', help='phpMyAdmin login page url')
    parser.add_argument('user', metavar='USERNAME', help='phpMyAdmin login username')
    parser.add_argument('password', metavar='PASSWORD', help='phpMyAdmin login password')
    parser.add_argument("-o", "--output-directory", default=os.getcwd(),
                        help="output directory for the SQL dump file (default: the current working directory)")
    parser.add_argument("-p", "--prepend-date", action="store_true", default=False,
                        help="prepend current UTC date & time to the filename; "
                             "see the --prefix-format option for custom formatting")
    parser.add_argument("-e", "--exclude-dbs", default="",
                        help="comma-separated list of database names to exclude from the dump")
    parser.add_argument("-s", "--server-name", default=None,
                        help="mysql server hostname to supply if enabled as field on login page")
    parser.add_argument("--compression", default="none", choices=["none", "zip", "gzip"],
                        help="compression method for the output file - must be supported by the server (default: %(default)s)")
    parser.add_argument("--basename", default=None,
                        help="the desired basename (without extension) of the SQL dump file (default: the name given "
                             "by phpMyAdmin); you can also set an empty basename "" in combination with "
                             "--prepend-date and --prefix-format")
    parser.add_argument("--timeout", type=int, default=60,
                        help="timeout in seconds for the requests (default: %(default)s)")
    parser.add_argument("--overwrite-existing", action="store_true", default=False,
                        help="overwrite existing SQL dump files (instead of appending a number to the name)")
    parser.add_argument("--prefix-format", default="",
                        help=str("the prefix format for --prepend-date (default: \"{}\"); in Python's strftime format. "
                                 "Must be used with --prepend-date to be in effect".format(
                                     DEFAULT_PREFIX_FORMAT.replace("%", "%%"))))
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="dry run, do not actually download any file")
    parser.add_argument("--http-auth", default=None,
                        help="Basic HTTP authentication, using format \"username:password\"")

    args = parser.parse_args()

    # if args.prefix_format and not args.prepend_date:
    #     print("Error: --prefix-format given without --prepend-date", file=sys.stderr)
    #     sys.exit(2)

    # try:
    #     dump_fn = download_mysql_backup(**vars(args))
    # except Exception as e:
    #     print('Error: {}'.format(e), file=sys.stderr)
    #     sys.exit(1)

    # print("{} saved SQL dump to: {}".format(('Would have' if args.dry_run else 'Successfully'), dump_fn),
    #       file=sys.stdout)
