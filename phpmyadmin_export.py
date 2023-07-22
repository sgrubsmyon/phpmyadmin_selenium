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
import datetime
import os
import sys
import re
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
# from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.common.by import By

DEFAULT_PREFIX_FORMAT = r'%Y-%m-%d_%H-%M-%S_UTC_'


def is_phpmyadmin_3(driver):
    page_source = str(driver.page_source.encode("utf-8"))
    frame_content_present = "frame_content" in page_source
    return frame_content_present


def is_login_successful(driver):
    page_source = str(driver.page_source.encode("utf-8"))
    frame_content_present = "frame_content" in page_source
    server_export_present = "server_export.php" in page_source
    return frame_content_present or server_export_present


def open_iframe(driver):
    iframe = driver.find_element(by=By.ID, value="frame_content")
    driver.switch_to.frame(iframe)


def splitext_special(filename):
    basename, ext = os.path.splitext(filename)
    if ext == ".gz":
        basename, ext = os.path.splitext(basename)
        ext = ext + ".gz"
    if ext == ".zip":
        basename, ext = os.path.splitext(basename)
        ext = ext + ".zip"
    return basename, ext


# get the downloaded file name (https://stackoverflow.com/questions/13317457/naming-a-file-when-downloading-with-selenium-webdriver)
def get_download_filename(dir, waitTime=5*60):
    os.chdir(dir)
    endTime = time.time() + waitTime
    while True:
        files = filter(os.path.isfile, os.listdir(dir))
        files = [os.path.join(dir, f) for f in files]  # add path to each file
        files.sort(key=lambda x: os.path.getmtime(x))
        newest_file = files[-1]
        extension = splitext_special(newest_file)[1]
        if extension != ".part":
            return os.path.basename(newest_file)
        time.sleep(1)
        # Prevent an infinite loop if something goes wrong:
        if time.time() > endTime:
            print('Error: Timeout of {} seconds reached on SQL backup file download'.format(
                waitTime), file=sys.stderr)
            sys.exit(1)


def download_mysql_backup(url, user, password, dry_run=False, overwrite_existing=False, prepend_date=True, basename=None,
                          output_directory=os.getcwd(), exclude_dbs=None, compression="none", prefix_format=None,
                          timeout=10, http_auth=None, server_name=None, **kwargs):
    prefix_format = prefix_format or DEFAULT_PREFIX_FORMAT

    options = Options()
    options.add_argument("-headless")

    # Firefox profiles deprecated
    # firefox_profile = FirefoxProfile()
    # firefox_profile.set_preference("browser.download.folderList", 2)
    # firefox_profile.set_preference("browser.download.manager.showWhenStarting", False)
    # firefox_profile.set_preference("browser.download.dir", output_directory)
    # firefox_profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "sql")
    # options.profile = firefox_profile

    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", output_directory)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "sql")

    driver = webdriver.Firefox(options=options)

    driver.implicitly_wait(timeout)

    if http_auth:
        # prepend 'username:password@' to the URL
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
        open_iframe(driver)

    #######################
    # Configure DB Export #
    #######################

    export_button = driver.find_element(
        By.CSS_SELECTOR, ".tab[href='server_export.php']")
    time.sleep(5)
    export_button.click()

    # Open the custom options
    custom_radio_button = driver.find_element(
        By.ID, "radio_custom_export")
    custom_radio_button.click()

    exclude_dbs = exclude_dbs.split(',') or []
    for db in exclude_dbs:
        if len(db) > 0:
            db_option = driver.find_element(
                by=By.CSS_SELECTOR, value="#db_select>option[value='{}']".format(db))
            db_option.click()

    compression_select = driver.find_element(by=By.ID, value="compression")
    compression_select.send_keys(compression)
    # time.sleep(5)

    ##########################
    # Download the DB export #
    ##########################

    go_button = driver.find_element(by=By.ID, value="buttonGo")
    # Scroll button into view so that it's clickable and not behind the "pma_console":
    driver.execute_script("arguments[0].scrollIntoView();", go_button)
    download_filename = "localhost.sql.gz" if compression == "gzip" else "localhost.sql.zip" if compression == "zip" else "localhost.sql"
    if not dry_run:
        go_button.click()
        src_filename = get_download_filename(output_directory)
        download_filename = src_filename
    if dry_run or download_filename.startswith("localhost"):
        download_filename = user + splitext_special(download_filename)[1]

    driver.quit()

    filename = download_filename if basename is None else basename + \
        splitext_special(download_filename)[1]
    if prepend_date:
        prefix = datetime.datetime.utcnow().strftime(prefix_format)
        filename = prefix + filename
    tgt_path = os.path.join(output_directory, filename)

    if os.path.isfile(tgt_path) and not overwrite_existing:
        basename, ext = splitext_special(tgt_path)
        n = 1
        print('File {} already exists, to overwrite it use --overwrite-existing'.format(
            tgt_path), file=sys.stderr)
        while True:
            alternate_tgt_path = '{}({}){}'.format(basename, n, ext)
            if not os.path.isfile(alternate_tgt_path):
                tgt_path = alternate_tgt_path
                break
            n += 1

    if not dry_run:
        # Rename the downloaded file to the desired filename:
        src_path = os.path.join(output_directory, src_filename)
        os.rename(src_path, tgt_path)

    return tgt_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="phpmyadmin_backup_down",
        description="Automated download of MySQL backup files from a phpMyAdmin "
                    "web interface, using just one command on the commandline.",
        epilog="Written by Markus Voge, rewritten from https://github.com/qubitstream/phpmyadmin_sql_backup, "
               "because it is defunct (actually its dependency grab is "
               "unmaintained and not working anymore since Python 3.10)."
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
    parser.add_argument("--timeout", type=int, default=10,
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
