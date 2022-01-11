from __future__ import print_function
from __future__ import print_function
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

from difflib import SequenceMatcher
import time
import pathlib
import platform
import requests
import logging
import mysql.connector
import cloudscraper
import json
import cv2
import os
import shutil, sys
import subprocess
from bs4 import BeautifulSoup
from datetime import datetime
from pyffmpeg import FFmpeg

def restart():
    import sys
    print("argv was",sys.argv)
    print("sys.executable was", sys.executable)
    print("restart now")

    import os
    os.execv(sys.executable, ['python'] + sys.argv)

if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(filename="logs/Scrap-JSON-Builder LOG", format='%(asctime)s %(message)s',
                    filemode='w')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Start Google drive API
# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']

"""Shows basic usage of the Drive v3 API.
Prints the names and ids of the first 10 files the user has access to.
"""
creds = None

while(True):
    break_out = False
    bypass_count = 0
    
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)
    
    #Get Cookie from text file
    cloudflare_cookie_file = open('cloudflare-cookie.txt', mode='r')
    CLOUDFLARE_COOKIE = cloudflare_cookie_file.read().strip()
    cloudflare_cookie_file.close()

    # To get these vars, please use google chrome network tools
    #CLOUDFLARE_COOKIE = 'cf_chl_prog=a12; cf_clearance=uZw2sSQrOusCDx4wM.NfChyKESF7.fym1tUKZBMQEC0-1633085787-0-150'
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36'

    headers = {
        'authority': 'anime-update.com',
        'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-ch-ua-mobile': '?0',
        'user-agent': USER_AGENT,
        'cookie': CLOUDFLARE_COOKIE,
        'sec-fetch-site': 'none',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-dest': 'document',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'accept-language': 'en-US,en;q=0.9',
        'accept-encoding': 'gzip, deflate'
    }

    # Check if anime already exists in the database
    DB = mysql.connector.connect(host='ftp.bagsplusportugal.com',
                                 database='animewatcher',
                                 user='animewatcher',
                                 password='FFigk#w5PHZQo*4F')

    if DB.is_connected() == False:
        # Log and error
        print("Could not connect to the database")
        logging.critical("Could not connect to the database")
        exit()
    cursor = DB.cursor()

    try:

        # Read file with series
        # myfile = open('anime-update-scraped.txt', 'r')
        myfile = open('copy2.txt', 'r')
        lines = myfile.readlines()

        line_number = 1

        animes = []
        for line in lines:

            # Remove last slash if there is any
            readable_line = line.strip()
            if readable_line[-1] == '/':
                readable_line = readable_line[:-1]

            # Get request to the page
            session = cloudscraper.create_scraper()
            page = session.get(readable_line + "/", headers=headers)

            if page.status_code != 200:
                # Log and error
                print("Got status code " + str(page.status_code) + " for " + readable_line + " (" + str(line_number) + ")")
                logging.critical(
                    "Got status code " + str(page.status_code) + " for " + readable_line + " (" + str(line_number) + ")")
                break

            # Start bs4
            soup = BeautifulSoup(page.content, "lxml")
            anime_info = soup.find("div", class_="row animeinfo-div")

            # Check if there is a temp file
            if not os.path.exists('temp/temp-anime-data.json'):

                # Log the start of the scrape
                print("Scrape started for " + readable_line.rsplit('/', 1)[-1] + " (" + str(line_number) + ")")
                logging.info("Scrape started for " + readable_line.rsplit('/', 1)[-1] + " (" + str(line_number) + ")")

                # Get anime name EN
                anime_name_tag = anime_info.find('h2')
                ANIME_NAME = anime_name_tag.b.text.replace("'", "").replace("?", "")

                # Get anime name JP
                single_episode_info = soup.find('div', class_="well episode_well")
                if single_episode_info is None:
                    single_episode_info = soup.find('div', class_="well special_well")

                if single_episode_info is not None:
                    span_with_anime_name = single_episode_info.find('div', class_="anime-title")
                    split_anime_name = span_with_anime_name.text.rsplit(" ", 2)[0]

                    if SequenceMatcher(None, ANIME_NAME.lower().strip(),
                                       split_anime_name.replace("?", "").lower().strip()).ratio() < 0.7:
                        ANIME_NAME_JP = split_anime_name.lower()
                    else:
                        ANIME_NAME_JP = None
                else:
                    ANIME_NAME_JP = None

                cursor.execute("select count(*) from Content_anime_class where mNameEN='" + ANIME_NAME.lower() + "';")
                records = cursor.fetchall()
                qtd = 0
                for row in records:
                    qtd = row[0]

                if qtd > 0:
                    # Log and error
                    print("Anime already in the database, skipping... (" + str(line_number) + ")")
                    logging.info("Anime already in the database, skipping... (" + str(line_number) + ")")
                    line_number += 1
                    continue

                # Get anime description
                anime_description_div = anime_info.find('div', class_="visible-md visible-lg")
                ANIME_DESCRIPTION = anime_description_div.text.replace('Description:', '').strip()

                # Get anime categories
                anime_category_tags = anime_info.find_all('a', class_="animeinfo_label")
                ANIME_CATEGORIES = []
                for a in anime_category_tags:
                    ANIME_CATEGORIES.append(a.span.text.strip())

                # Get anime thumbnail
                ANIME_THUMBNAIL = ""

                # Get on going
                anime_ongoing_tags = anime_info.find_all('p')
                if anime_ongoing_tags[2].text.find("Completed") != -1:
                    ANIME_ONGOING = False
                else:
                    ANIME_ONGOING = True
            else:

                # Get file data
                with open('temp/temp-anime-data.json', 'r') as json_file:
                    temp_json_data = json.load(json_file)

                    if temp_json_data["line"] != line_number:
                        line_number += 1
                        continue

                    print('Temp file found! Starting from ' + temp_json_data["mNameEN"] + '...')
                    logging.info('Temp file found! Starting from ' + temp_json_data["mNameEN"] + '...')

                    # Load anime data
                    ANIME_NAME = temp_json_data["mNameEN"]
                    ANIME_DESCRIPTION = temp_json_data["mDescription"]
                    ANIME_CATEGORIES = temp_json_data["mCategories"]
                    ANIME_THUMBNAIL = temp_json_data["mThumbnail"]
                    ANIME_ONGOING = temp_json_data["mOnGoing"]
                    EPISODES_json_temp = temp_json_data["episodes"]
                    ANIME_FOLDER_ID = temp_json_data["anime-folder"]
                    ANIME_THUMBNAILS_FOLDER_ID = temp_json_data["anime-thumbnails-folder"]
                    ANIME_NAME_JP = temp_json_data["mNameJP"]

            # Get anime episodes

            # get the normal episode links
            ANIME_EPISODE_LINKS = []
            ANIME_EPISODE_DATES = []
            anime_tabcontent_div = soup.find("div", {"id": "eps"})
            anime_episode_div = anime_tabcontent_div.find("div", class_="col-sm-6")
            anime_episode_tags = anime_episode_div.find_all("a", class_="episode_well_link")
            for a in anime_episode_tags:
                ANIME_EPISODE_LINKS.append("https://anime-update.com" + a['href'])
                span = a.find("span", class_="label pull-right animeupdate-color")
                date = span.text.strip().split(" ")
                # Make sure the day has 2 digits
                day = str(date[0])
                day = day.zfill(2)

                if date[1] == "January":
                    ANIME_EPISODE_DATES.append(date[2] + "-01-" + day + " 00:00:00.000000")
                elif date[1] == "February":
                    ANIME_EPISODE_DATES.append(date[2] + "-02-" + day + " 00:00:00.000000")
                elif date[1] == "March":
                    ANIME_EPISODE_DATES.append(date[2] + "-03-" + day + " 00:00:00.000000")
                elif date[1] == "April":
                    ANIME_EPISODE_DATES.append(date[2] + "-04-" + day + " 00:00:00.000000")
                elif date[1] == "May":
                    ANIME_EPISODE_DATES.append(date[2] + "-05-" + day + " 00:00:00.000000")
                elif date[1] == "June":
                    ANIME_EPISODE_DATES.append(date[2] + "-06-" + day + " 00:00:00.000000")
                elif date[1] == "July":
                    ANIME_EPISODE_DATES.append(date[2] + "-07-" + day + " 00:00:00.000000")
                elif date[1] == "August":
                    ANIME_EPISODE_DATES.append(date[2] + "-08-" + day + " 00:00:00.000000")
                elif date[1] == "September":
                    ANIME_EPISODE_DATES.append(date[2] + "-09-" + day + " 00:00:00.000000")
                elif date[1] == "October":
                    ANIME_EPISODE_DATES.append(date[2] + "-10-" + day + " 00:00:00.000000")
                elif date[1] == "November":
                    ANIME_EPISODE_DATES.append(date[2] + "-11-" + day + " 00:00:00.000000")
                elif date[1] == "December":
                    ANIME_EPISODE_DATES.append(date[2] + "-12-" + day + " 00:00:00.000000")

            # get special episode links
            ANIME_SPECIAL_EPISODE_LINKS = []
            ANIME_SPECIAL_EPISODE_DATES = []
            anime_tabcontent_div = soup.find("div", {"id": "specials"})

            if anime_tabcontent_div is not None:
                anime_episode_tags = anime_tabcontent_div.find_all("a")
                for a in anime_episode_tags:
                    ANIME_SPECIAL_EPISODE_LINKS.append("https://anime-update.com" + a['href'])
                    span = a.find("span", class_="label pull-right animeupdate-color front_time")
                    date = span.text.strip().split(" ")
                    # Make sure the day has 2 digits
                    day = str(date[0])
                    day = day.zfill(2)

                    if date[1] == "January":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-01-" + day + " 00:00:00.000000")
                    elif date[1] == "February":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-02-" + day + " 00:00:00.000000")
                    elif date[1] == "March":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-03-" + day + " 00:00:00.000000")
                    elif date[1] == "April":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-04-" + day + " 00:00:00.000000")
                    elif date[1] == "May":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-05-" + day + " 00:00:00.000000")
                    elif date[1] == "June":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-06-" + day + " 00:00:00.000000")
                    elif date[1] == "July":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-07-" + day + " 00:00:00.000000")
                    elif date[1] == "August":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-08-" + day + " 00:00:00.000000")
                    elif date[1] == "September":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-09-" + day + " 00:00:00.000000")
                    elif date[1] == "October":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-10-" + day + " 00:00:00.000000")
                    elif date[1] == "November":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-11-" + day + " 00:00:00.000000")
                    elif date[1] == "December":
                        ANIME_SPECIAL_EPISODE_DATES.append(date[2] + "-12-" + day + " 00:00:00.000000")

            print("Anime info added!")
            logging.info("Anime info added!")

            print("Fetching episodes...")
            logging.info("Fetching episodes...")

            there_are_specials = False
            if os.path.exists('temp/temp-anime-data.json'):
                EPISODES = EPISODES_json_temp
                there_are_specials = False
                for ep in EPISODES:
                    if ep["mIsSpecial"] == True:
                        there_are_specials = True
            else:
                EPISODES = []

            if there_are_specials == False:
                # Read normal episodes
                alternative_counter = 1
                temp_counter = 0
                for ep_link, ep_date in zip(ANIME_EPISODE_LINKS, ANIME_EPISODE_DATES):
                    episode = {}

                    ANIME_EPISODE_IS_SPECIAL = False

                    # Episode number
                    episode_denominator = ep_link[:-1].rsplit('/', 1)[-1]
                    split_denominator = episode_denominator.split("-")
                    if split_denominator[-1].isdigit():
                        ANIME_EPISODE_NUMBER = int(split_denominator[-1])
                    else:
                        ANIME_EPISODE_NUMBER = alternative_counter
                        alternative_counter += 1

                    if os.path.exists('temp/temp-anime-data.json'):
                        if temp_counter < len(EPISODES_json_temp):
                            if EPISODES_json_temp[temp_counter]["mEpisodeNumber"] >= ANIME_EPISODE_NUMBER:
                                temp_counter += 1
                                continue

                    # Episode Release Date
                    ANIME_EPISODE_RELEASE_DATE = ep_date

                    # Make Episode Request
                    episode_session = cloudscraper.create_scraper()
                    episode_page = episode_session.get(ep_link, headers=headers)

                    if episode_page.status_code != 200:
                        # Log and error
                        print(
                            "Got status code " + str(episode_page.status_code) + " for " + ep_link + " (" + str(
                                line_number) + ")")
                        logging.warning(
                            "Got status code " + str(episode_page.status_code) + " for " + ep_link + " (" + str(
                                line_number) + ")")

                        exit()

                    # Start bs4
                    episode_soup = BeautifulSoup(episode_page.content, "lxml")

                    # Episode name
                    episode_info = episode_soup.find("table", class_="episode_title_table hidden-xs")
                    title_info = episode_info.find("h4")
                    ANIME_EPISODE_TITLE = title_info.text.strip()

                    # Episode Video Link
                    episode_player_wraper = episode_soup.find("div", {"id": "videocontent"})
                    episode_player = episode_player_wraper.find("div", {"id": "fembed"})

                    try:

                        if episode_player is not None:

                            ANIME_EPISODE_IS_VCDN = True
                            episode_player_js = episode_soup.find_all("script")
                            for script in episode_player_js:

                                function_check = script.string
                                if function_check is None:
                                    continue

                                strip_function_check = function_check.strip()

                                if strip_function_check[0:8] == "function":
                                    js_name_verifier = strip_function_check[9:]

                                    if js_name_verifier[:js_name_verifier.find("()")] == 'fembed':
                                        vide_iframe_innerHTML = js_name_verifier[js_name_verifier.find("<iframe"):-3]
                                        video_iframe = BeautifulSoup(vide_iframe_innerHTML, "lxml")
                                        video_iframe_bs4 = video_iframe.find("iframe")
                                        video_src = video_iframe_bs4["src"]

                                        # Get true url
                                        url_session = cloudscraper.create_scraper()
                                        true_url_page = url_session.get("https://anime-update.com" + video_src,
                                                                        headers=headers,
                                                                        stream=True)

                                        ANIME_EPISODE_VIDEO_URL = true_url_page.url
                                    else:
                                        continue
                                else:
                                    continue

                            # Episode Length Secs
                            if ANIME_EPISODE_VIDEO_URL[-1] == '/':
                                ANIME_EPISODE_VIDEO_URL = ANIME_EPISODE_VIDEO_URL[:-1]
                            ANIME_EPISODE_DURATION = "0"

                        else:
                            # Log and warn
                            print("There is no VCDN player for " + ep_link + " (" + str(line_number) + ")")
                            logging.warning(
                                "There is no VCDN player for " + ep_link + " (" + str(line_number) + ")")

                            ANIME_EPISODE_IS_VCDN = False
                            ANIME_EPISODE_VIDEO_URL = ''

                            # Delete temp file if exists
                            if os.path.exists('temp/temp-anime-data.json'):
                                os.remove("temp/temp-anime-data.json")

                            # Save data on a file
                            json_anime = {
                                "line": line_number,
                                "anime-folder": ANIME_FOLDER_ID,
                                "anime-thumbnails-folder": ANIME_THUMBNAILS_FOLDER_ID,
                                "mNameEN": ANIME_NAME,
                                "mNameJP": ANIME_NAME_JP,
                                "mDescription": ANIME_DESCRIPTION,
                                "mCategories": ANIME_CATEGORIES,
                                "mThumbnail": ANIME_THUMBNAIL,
                                "mOnGoing": ANIME_ONGOING,
                                "episodes": EPISODES
                            }

                            if not os.path.exists('temp'):
                                os.makedirs('temp')

                            with open("temp/temp-anime-data.json", "w") as json_file:
                                json.dump(json_anime, json_file, indent=4)

                            # Decide what to do based on the OS
                            if platform.system().lower() != "windows":
                                # Log and warn
                                print("There are no compatible players for " + ep_link + " (" + str(line_number) + ")")
                                logging.critical(
                                    "There are no compatible players for " + ep_link + " (" + str(line_number) + ")")
                                exit()
                            else:
                                if bypass_count > 0:
                                    # Log and warn
                                    print("There are no compatible players for " + ep_link + " (" + str(line_number) + ")")
                                    logging.critical(
                                        "There are no compatible players for " + ep_link + " (" + str(line_number) + ")")
                                    exit()

                                # Log and warn
                                print("There are no compatible players for " + ep_link + " (" + str(line_number) + "), running bypass...")
                                logging.warning(
                                    "There are no compatible players for " + ep_link + " (" + str(line_number) + "), running bypass...")

                                #subprocess.run(["psexec", "cmd.exe", "/c", "start", str(pathlib.Path().resolve()) + "\\reset_silent.bat"])
                                #time.sleep(10)
                                '''bypass_count += 1
                                break_out = True
                                break'''
                                exit()

                        print("Calculating video length for " + ANIME_EPISODE_VIDEO_URL + " (" + str(line_number) + ")")
                        logging.info("Calculating video length for " + ANIME_EPISODE_VIDEO_URL + " (" + str(line_number) + ")")

                        ANIME_EPISODE_DURATION = "0"
                        ANIME_EPISODE_THUMBNAIL_IMAGE = ""

                    except Exception as ex:
                        print(ex)
                        ANIME_EPISODE_THUMBNAIL_IMAGE = ''
                        ANIME_EPISODE_DURATION = str(0)
                        ANIME_EPISODE_IS_VCDN = False
                        print("Couldnt fetch " + ANIME_NAME + " episode " + str(
                            ANIME_EPISODE_NUMBER) + " skipping for now - " + " (" + str(line_number) + ")")
                        logging.critical("Couldnt fetch " + ANIME_NAME + " episode " + str(
                            ANIME_EPISODE_NUMBER) + " skipping for now - " + " (" + str(line_number) + ")")

                    episode = {
                        "mEpisodeNumber": ANIME_EPISODE_NUMBER,
                        "mNameEN": ANIME_EPISODE_TITLE.lower(),
                        "mNameJP": None,
                        "mLengthSecs": ANIME_EPISODE_DURATION,
                        "mViews": 0,
                        "mReleaseDate": ANIME_EPISODE_RELEASE_DATE,
                        "mVideoFileLink": ANIME_EPISODE_VIDEO_URL,
                        "mThumbnail": ANIME_EPISODE_THUMBNAIL_IMAGE,
                        "mVCDN": ANIME_EPISODE_IS_VCDN,
                        "mIsSpecial": ANIME_EPISODE_IS_SPECIAL
                    }

                    EPISODES.append(episode)
                    temp_counter += 1
                    
            if break_out:
                break

            # Read special episodes
            alternative_counter = 1
            for ep_link, ep_date in zip(ANIME_SPECIAL_EPISODE_LINKS, ANIME_SPECIAL_EPISODE_DATES):
                episode = {}

                ANIME_EPISODE_IS_SPECIAL = True

                # Episode number
                episode_denominator = ep_link[:-1].rsplit('/', 1)[-1]
                split_denominator = episode_denominator.split("-")
                if split_denominator[-1].isdigit():
                    ANIME_EPISODE_NUMBER = int(split_denominator[-1])
                else:
                    qtd = 0
                    for ep_in_list in EPISODES:
                        if ep_in_list['mIsSpecial']:
                            qtd += 1

                    if qtd > 0:
                        ANIME_EPISODE_NUMBER = qtd
                    else:                        
                        ANIME_EPISODE_NUMBER = alternative_counter
                        alternative_counter += 1

                if os.path.exists('temp/temp-anime-data.json') and there_are_specials:
                    already = False
                    for ep in EPISODES_json_temp:
                        if ep["mIsSpecial"] == True and ep["mEpisodeNumber"] == ANIME_EPISODE_NUMBER:
                            already = True
                    if already:
                        continue

                # Episode Release Date
                ANIME_EPISODE_RELEASE_DATE = ep_date

                # Make Episode Request
                episode_session = cloudscraper.create_scraper()
                episode_page = episode_session.get(ep_link, headers=headers)

                if episode_page.status_code != 200:
                    # Log and error
                    print(
                        "Got status code " + str(episode_page.status_code) + " for " + ep_link + " (" + str(
                            line_number) + ")")
                    logging.critical(
                        "Got status code " + str(episode_page.status_code) + " for " + ep_link + " (" + str(
                            line_number) + ")")
                    exit()

                # Start bs4
                episode_soup = BeautifulSoup(episode_page.content, "lxml")

                # Episode name
                episode_info = episode_soup.find("table", class_="episode_title_table hidden-xs")
                title_info = episode_info.find("h4")
                ANIME_EPISODE_TITLE = title_info.text.strip()

                # Episode Video Link
                episode_player_wraper = episode_soup.find("div", {"id": "videocontent"})
                episode_player = episode_player_wraper.find("div", {"id": "fembed"})

                try:

                    if episode_player is not None:

                        ANIME_EPISODE_IS_VCDN = True
                        episode_player_js = episode_soup.find_all("script")
                        for script in episode_player_js:

                            function_check = script.string
                            if function_check is None:
                                continue

                            strip_function_check = function_check.strip()

                            if strip_function_check[0:8] == "function":
                                js_name_verifier = strip_function_check[9:]

                                if js_name_verifier[:js_name_verifier.find("()")] == 'fembed':
                                    vide_iframe_innerHTML = js_name_verifier[js_name_verifier.find("<iframe"):-3]
                                    video_iframe = BeautifulSoup(vide_iframe_innerHTML, "lxml")
                                    video_iframe_bs4 = video_iframe.find("iframe")
                                    video_src = video_iframe_bs4["src"]

                                    # Get true url
                                    url_session = cloudscraper.create_scraper()
                                    true_url_page = url_session.get("https://anime-update.com" + video_src, headers=headers,
                                                                    stream=True)

                                    ANIME_EPISODE_VIDEO_URL = true_url_page.url
                                    break
                                else:
                                    continue
                            else:
                                continue

                        # Episode Length Secs

                    else:
                        # Log and warn
                        print("There is no VCDN player for " + ep_link + ", trying Video (" + str(line_number) + ")")
                        logging.warning(
                            "There is no VCDN player for " + ep_link + ", trying Video (" + str(line_number) + ")")

                        ANIME_EPISODE_IS_VCDN = False
                        ANIME_EPISODE_VIDEO_URL = ''

                        # Delete temp file if exists
                        if os.path.exists('temp/temp-anime-data.json'):
                            os.remove("temp/temp-anime-data.json")

                        # Save data on a file
                        json_anime = {
                            "line": line_number,
                            "anime-folder": ANIME_FOLDER_ID,
                            "anime-thumbnails-folder": ANIME_THUMBNAILS_FOLDER_ID,
                            "mNameEN": ANIME_NAME,
                            "mNameJP": ANIME_NAME_JP,
                            "mDescription": ANIME_DESCRIPTION,
                            "mCategories": ANIME_CATEGORIES,
                            "mThumbnail": ANIME_THUMBNAIL,
                            "mOnGoing": ANIME_ONGOING,
                            "episodes": EPISODES
                        }

                        if not os.path.exists('temp'):
                            os.makedirs('temp')

                        with open("temp/temp-anime-data.json", "w") as json_file:
                            json.dump(json_anime, json_file, indent=4)

                        # Decide what to do based on the OS
                        if platform.system().lower() != "windows":
                            # Log and warn
                            print("There are no compatible players for " + ep_link + " (" + str(line_number) + ")")
                            logging.critical(
                                "There are no compatible players for " + ep_link + " (" + str(line_number) + ")")
                            exit()
                        else:
                            if bypass_count > 0:
                                # Log and warn
                                print("There are no compatible players for " + ep_link + " (" + str(line_number) + ")")
                                logging.critical(
                                    "There are no compatible players for " + ep_link + " (" + str(line_number) + ")")
                                exit()

                            # Log and warn
                            print("There are no compatible players for " + ep_link + " (" + str(line_number) + "), running bypass...")
                            logging.warning(
                                "There are no compatible players for " + ep_link + " (" + str(line_number) + "), running bypass...")

                            #subprocess.run(["psexec", "cmd.exe", "/c", "start", str(pathlib.Path().resolve()) + "\\reset_silent.bat"])
                            #time.sleep(10)
                            '''bypass_count += 1
                            break_out = True
                            break'''
                            exit()

                    print("Calculating video length for (" + str(line_number) + ")")
                    logging.info("Calculating video length for (" + str(line_number) + ")")

                    ANIME_EPISODE_DURATION = "0"
                    ANIME_EPISODE_THUMBNAIL_IMAGE = ""

                except Exception as ex:
                    print(ex)
                    ANIME_EPISODE_THUMBNAIL_IMAGE = ''
                    ANIME_EPISODE_IS_VCDN = False
                    ANIME_EPISODE_DURATION = str(0)
                    print("Couldnt fetch " + ANIME_NAME + " episode " + str(
                        ANIME_EPISODE_NUMBER) + " skipping for now - (" + str(line_number) + ")")
                    logging.critical("Couldnt fetch " + ANIME_NAME + " episode " + str(
                        ANIME_EPISODE_NUMBER) + " skipping for now - (" + str(line_number) + ")")

                episode = {
                    "mEpisodeNumber": ANIME_EPISODE_NUMBER,
                    "mNameEN": ANIME_EPISODE_TITLE.lower(),
                    "mNameJP": None,
                    "mLengthSecs": ANIME_EPISODE_DURATION,
                    "mViews": 0,
                    "mReleaseDate": ANIME_EPISODE_RELEASE_DATE,
                    "mVideoFileLink": ANIME_EPISODE_VIDEO_URL,
                    "mThumbnail": ANIME_EPISODE_THUMBNAIL_IMAGE,
                    "mVCDN": ANIME_EPISODE_IS_VCDN,
                    "mIsSpecial": ANIME_EPISODE_IS_SPECIAL
                }

                EPISODES.append(episode)
            
            if break_out:
                break
            
            # Add anime to DB
            if ANIME_NAME_JP is not None and ANIME_NAME_JP != "" and ANIME_NAME_JP != " ":
                cursor.execute("insert into Content_anime_class values (%s, %s, %s, %s, %s, %s);",
                               (ANIME_NAME.lower(), ANIME_NAME_JP.lower().strip(), ANIME_DESCRIPTION, ANIME_THUMBNAIL,
                                len(EPISODES), ANIME_ONGOING))
            else:
                cursor.execute("insert into Content_anime_class values (%s, %s, %s, %s, %s, %s);",
                               (ANIME_NAME.lower(), None, ANIME_DESCRIPTION, ANIME_THUMBNAIL, len(EPISODES), ANIME_ONGOING))

            DB.commit()

            # Add anime categories to DB
            for genre in ANIME_CATEGORIES:
                cursor.execute("insert into Content_anime_class_mCategories values(%s, %s, %s);",
                               (None, ANIME_NAME.lower(), genre.lower()))
                DB.commit()

                cursor.execute(
                    "update Content_category_class set mAnimeCount=mAnimeCount+1 where mCategoryName='" + genre.lower() + "'")
                DB.commit()

            # Add episodes to DB
            for ep in EPISODES:
                # Add to DB
                cursor.execute("insert into Content_episode_class values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                               (None, ep["mEpisodeNumber"], ep["mNameEN"], None, ep["mLengthSecs"], 0,
                                ep["mReleaseDate"], ep["mThumbnail"], ANIME_NAME.lower(), ep["mVideoFileLink"], ep["mVCDN"],
                                ep["mIsSpecial"]))
                DB.commit()

            print("Anime " + ANIME_NAME + " added successfully!" + " (" + str(line_number) + ")")
            logging.info("Anime " + ANIME_NAME + " added successfully!" + " (" + str(line_number) + ")")

            # Delete temp file if exists
            if os.path.exists('temp/temp-anime-data.json'):
                os.remove("temp/temp-anime-data.json")

            line_number += 1

        myfile.close()
        if break_out:
            continue
        else:
            break

    except KeyboardInterrupt:
        if len(EPISODES) > 0:
            # Delete temp file if exists
            if os.path.exists('temp/temp-anime-data.json'):
                os.remove("temp/temp-anime-data.json")

            # Save data on a file
            json_anime = {
                "line": line_number,
                "anime-folder": ANIME_FOLDER_ID,
                "anime-thumbnails-folder": ANIME_THUMBNAILS_FOLDER_ID,
                "mNameEN": ANIME_NAME,
                "mNameJP": ANIME_NAME_JP,
                "mDescription": ANIME_DESCRIPTION,
                "mCategories": ANIME_CATEGORIES,
                "mThumbnail": ANIME_THUMBNAIL,
                "mOnGoing": ANIME_ONGOING,
                "episodes": EPISODES
            }

            if not os.path.exists('temp'):
                os.makedirs('temp')

            with open("temp/temp-anime-data.json", "w") as json_file:
                json.dump(json_anime, json_file, indent=4)
        exit()
