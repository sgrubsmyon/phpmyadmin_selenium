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
# Based on https://github.com/qubitstream/phpmyadmin_sql_backup, which
# is defunct (actually its dependency grab is unmaintained and not working
# anymore since Python 3.10. As of 2023-07-18, only version 0.6.41 of grab
# from 2018-06-24 is on PyPI, but support for Python 3.10 was added only in
# 2022-02-24, see https://github.com/lorien/grab/issues/394).
#
# tested on Python 3.10
# requires: selenium (https://www.selenium.dev/)
#
# Markus Voge, 2023-07

import argparse
import os
import sys
import re
from time import sleep

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

DEFAULT_PREFIX_FORMAT = r'%Y-%m-%d--%H-%M-%S-UTC_'


def is_phpmyadmin_3(driver):
    page_source = str(driver.page_source.encode("utf-8"))
    frame_content_present = "frame_content" in page_source
    return frame_content_present


def is_login_successful(driver):
    page_source = str(driver.page_source.encode("utf-8"))
    frame_content_present = "frame_content" in page_source
    server_export_present = "server_export.php" in page_source
    return frame_content_present or server_export_present


def open_frame(driver):
    frame = driver.find_element(by=By.ID, value="frame_content")
    frame_url = frame.get_attribute("src")
    driver.get(frame_url)


def download_mysql_backup(url, user, password, dry_run=False, overwrite_existing=False, prepend_date=True, basename=None,
                          output_directory=os.getcwd(), exclude_dbs=None, compression="none", prefix_format=None,
                          timeout=60, http_auth=None, server_name=None, **kwargs):
    prefix_format = prefix_format or DEFAULT_PREFIX_FORMAT
    exclude_dbs = exclude_dbs.split(',') or []
    encoding = '' if compression == 'gzip' else 'gzip'

    chrome_options = Options()
    # chrome_options.add_argument('--headless')
    # fix the "DevToolsActivePort file doesn't exist" error (https://stackoverflow.com/questions/56637973/how-to-fix-selenium-devtoolsactiveport-file-doesnt-exist-exception-in-python)
    chrome_options.add_argument("--remote-debugging-port=9222")
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(30)

    if http_auth:
        url = re.sub("^(https?:\/\/)(.*)$", "\\1{}@\\2".format(http_auth), url)

    driver.get(url)

    #########
    # Login #
    #########

    username_box = driver.find_element(by=By.ID, value="input_username")
    password_box = driver.find_element(by=By.ID, value="input_password")
    server_box = None
    if server_name:
        server_box = driver.find_element(by=By.ID, value="input_servername")
    submit_button = driver.find_element(by=By.ID, value="input_go")

    username_box.send_keys(user)
    password_box.send_keys(password)
    if server_name:
        server_box.send_keys(server_name)
    submit_button.click()

    if not is_login_successful(driver):
        raise ValueError(
            "Could not login - did you provide the correct username and password?")

    if is_phpmyadmin_3(driver):
        open_frame(driver)

    #######################
    # Configure DB Export #
    #######################

    export_button = driver.find_element(
        by=By.CSS_SELECTOR, value=".tab[href='server_export.php']")
    export_button.click()

    # Open the custom options
    custom_radio_button = driver.find_element(
        by=By.ID, value="radio_custom_export")
    custom_radio_button.click()

    for db in exclude_dbs:
        if len(db) > 0:
            db_option = driver.find_element(
                by=By.CSS_SELECTOR, value="#db_select>option[value='{}']".format(db))
            db_option.click()

    compression_select = driver.find_element(by=By.ID, value="compression")
    compression_select.send_keys(compression)
    sleep(5)

    go_button = driver.find_element(by=By.ID, value="buttonGo")
    # go_button.click()

    driver.quit()


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
    parser.add_argument('user', metavar='USERNAME',
                        help='phpMyAdmin login username')
    parser.add_argument('password', metavar='PASSWORD',
                        help='phpMyAdmin login password')
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

    if args.prefix_format and not args.prepend_date:
        print("Error: --prefix-format given without --prepend-date", file=sys.stderr)
        sys.exit(2)

    try:
        dump_fn = download_mysql_backup(**vars(args))
    except Exception as e:
        print('Error: {}'.format(e), file=sys.stderr)
        sys.exit(1)

    print("{} saved SQL dump to: {}".format(('Would have' if args.dry_run else 'Successfully'), dump_fn),
          file=sys.stdout)
