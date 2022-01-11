from __future__ import print_function
from __future__ import print_function
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

from difflib import SequenceMatcher
from datetime import datetime, timedelta
import requests
import logging
import mysql.connector
import cloudscraper
import json
import cv2
import os
import time
import shutil, sys
import subprocess
from bs4 import BeautifulSoup
from datetime import datetime
from pyffmpeg import FFmpeg

if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(filename="logs/New-Anime_Scraper LOG - ", format='%(asctime)s %(message)s',
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

while True:

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

    # Get Cookie from text file
    cloudflare_cookie_file = open('cloudflare-cookie.txt', mode='r')
    CLOUDFLARE_COOKIE = cloudflare_cookie_file.read().strip()
    cloudflare_cookie_file.close()

    # CLOUDFLARE_COOKIE = 'cf_chl_prog=a10; cf_clearance=8oJ1d9aMQWfEK3oa7E3IEB2IUbMj4u3jTGlHKpmz9OE-1631716947-0-150; __cf_bm=aMWIaCoPzoRE1iAoIz4QMyKJCJV.BNRJCLbBkiVK0Eo-1631716949-0-AUS3m8vobuz7Tnt395bbngxvyDSTA2c3Jh440aA1i7QFAIvWrEXiyqHkjBVUcnaoHTEZ0DhcuVVi2HdeJ5tuqpppOESJSU1GvEg7qoJEytqDd/tg1PVQSroawY2PXYkxyA=='
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36'
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

    URL = "https://anime-update.com"

    # Check if anime already exists in the database
    DB = mysql.connector.connect(host='',
                                 database='',
                                 user='',
                                 password='')

    if not DB.is_connected():
        # Log and error
        print("Could not connect to the database")
        logging.critical("Could not connect to the database")
        exit()
    cursor = DB.cursor()

    # Get all new episodes
    session = cloudscraper.create_scraper()
    page = session.get(URL, headers=headers)

    if page.status_code != 200:
        # Log and error
        print("Got status code " + str(page.status_code) + " for " + URL)
        logging.critical(
            "Got status code " + str(page.status_code) + " for " + URL)
        break

    # Start bs4
    soup = BeautifulSoup(page.content, "lxml")
    new_anime_info = soup.find("div", {"id": "latest"})

    # Scrape episode items
    episode_items = new_anime_info.find_all("div", class_="latestep_wrapper")

    if episode_items is not None:

        for item in episode_items:
            # Check if anime is in the Database
            span_anime_title = item.find("a", class_="latest-parent")
            ANIME_NAME = span_anime_title["title"].strip().replace("'", "").replace("?", "")

            # Make the Query
            cursor.execute("select count(*) from Content_anime_class where mNameEN='" + ANIME_NAME.lower() + "';")
            records = cursor.fetchall()
            qtd = 0
            for row in records:
                qtd = row[0]

            if qtd > 0:  # If there is an anime, then add the episode

                # Check if its special
                episode_title_string_span = item.find("span", class_="latestep_title")
                if episode_title_string_span is None:
                    episode_title_string_span = item.find("span", class_="latestep_stitle")

                episode_title_string = episode_title_string_span.find("a")

                ANIME_EPISODE_LINK = URL + episode_title_string["href"]

                if episode_title_string.text.strip().split(" ")[-1].isdigit() == False:
                    ep_title_compare_string = episode_title_string.text.strip().split(" ")[-3]

                    if episode_title_string.text.strip().split(" ")[-2].isdigit():
                        temporary_episode_number = int(episode_title_string.text.strip().split(" ")[-2])
                    else:
                        temporary_episode_number = 1
                else:
                    ep_title_compare_string = episode_title_string.text.strip().split(" ")[-2]

                    if episode_title_string.text.strip().split(" ")[-1].isdigit():
                        temporary_episode_number = int(episode_title_string.text.strip().split(" ")[-1])
                    else:
                        temporary_episode_number = 1

                if ep_title_compare_string == "Episode":
                    ANIME_EPISODE_IS_SPECIAL = False
                    ANIME_EPISODE_NUMBER = temporary_episode_number
                else:
                    ANIME_EPISODE_IS_SPECIAL = True
                    ANIME_EPISODE_NUMBER = temporary_episode_number

                # Check if the episode already exists
                if ANIME_EPISODE_IS_SPECIAL:
                    cursor.execute(
                        "select count(*) from Content_episode_class where mAnime_id='" + ANIME_NAME.lower() + "' and mIsSpecial=1 and mEpisodeNumber='" + str(
                            ANIME_EPISODE_NUMBER) + "';")
                else:
                    cursor.execute(
                        "select count(*) from Content_episode_class where mAnime_id='" + ANIME_NAME.lower() + "' and mIsSpecial=0 and mEpisodeNumber='" + str(
                            ANIME_EPISODE_NUMBER) + "';")
                records = cursor.fetchall()
                episode_qtd = 0
                for row in records:
                    episode_qtd = row[0]

                if episode_qtd > 0:
                    print(ANIME_NAME.lower() + " - " + str(ANIME_EPISODE_NUMBER))

                    # Log and error
                    print("Episode already exists, skipping... - ")
                    logging.warning("Episode already exists, skipping... - ")
                    continue

                # Get release date
                release_date_span = item.find("span", class_="label label-latestep label-timeago")
                if "day" not in release_date_span.text.strip().lower():
                    d = datetime.today() - timedelta(hours=int(release_date_span.text.strip().split(" ")[0]))
                else:
                    d = datetime.today() - timedelta(days=int(release_date_span.text.strip().split(" ")[0]))

                ANIME_EPISODE_RELEASE_DATE = d.strftime("%Y") + "-" + d.strftime("%m") + "-" + d.strftime(
                    "%d") + " " + d.strftime("%H") + ":" + d.strftime("%m") + ":00.000000"

                # Make Episode Request
                episode_session = cloudscraper.create_scraper()
                episode_page = episode_session.get(ANIME_EPISODE_LINK, headers=headers)

                if episode_page.status_code != 200:
                    # Log and error
                    print(
                        "Got status code " + str(episode_page.status_code) + " for " + ANIME_EPISODE_LINK)
                    logging.critical(
                        "Got status code " + str(episode_page.status_code) + " for " + ANIME_EPISODE_LINK)
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

                        vcdn_url = "https://vcdn2.space/api/source/" + ANIME_EPISODE_VIDEO_URL.rsplit('/', 1)[-1]

                        vcdn_payload = "r=&d=vcdn2.space"
                        vcdn_headers = {
                            'authority': 'vcdn2.space',
                            'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
                            'accept': '*/*',
                            'x-requested-with': 'XMLHttpRequest',
                            'sec-ch-ua-mobile': '?0',
                            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
                            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            'origin': 'https://vcdn2.space',
                            'sec-fetch-site': 'same-origin',
                            'sec-fetch-mode': 'cors',
                            'sec-fetch-dest': 'empty',
                            'referer': ANIME_EPISODE_VIDEO_URL,
                            'accept-language': 'en-US,en;q=0.9'
                        }

                        vcdn_response = requests.request("POST", vcdn_url, headers=vcdn_headers, data=vcdn_payload)
                        vcdn_data = vcdn_response.json()

                        vcdn_redirect_link = ''
                        for d in vcdn_data['data']:
                            vcdn_redirect_link = d['file']

                        vcdn_r = requests.get(vcdn_redirect_link, stream=True, verify=False)

                        TRUE_URL = vcdn_r.url

                    else:
                        # Log and warn
                        print("There is no VCDN player for " + ep_link + ", trying Video")
                        logging.warning(
                            "There is no VCDN player for " + ep_link + ", trying Video")

                        episode_player = episode_player_wraper.find("div", {"id": "gstore"})

                        if episode_player is None:
                            break

                        ANIME_EPISODE_IS_VCDN = False

                        episode_player_js = episode_soup.find_all("script")
                        for script in episode_player_js:

                            function_check = script.string
                            if function_check is None:
                                continue

                            strip_function_check = function_check.strip()

                            if strip_function_check[0:8] == "function":
                                js_name_verifier = strip_function_check[9:]

                                if js_name_verifier[:js_name_verifier.find("()")] == 'gstore':
                                    video_src = js_name_verifier[
                                                js_name_verifier.find("/redirect/"):js_name_verifier.find(
                                                    "', type: 'video/mp4'")]

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

                        TRUE_URL = ANIME_EPISODE_VIDEO_URL

                    print("Calculating video length for " + TRUE_URL)
                    logging.info("Calculating video length for " + TRUE_URL)

                    try:
                        video = cv2.VideoCapture(TRUE_URL)
                        frames = video.get(cv2.CAP_PROP_FRAME_COUNT)
                        fps = int(video.get(cv2.CAP_PROP_FPS))
                        seconds = int(frames / fps)

                        ANIME_EPISODE_DURATION = str(seconds)

                        # Get thumbnail file ID
                        cursor.execute(
                            "select mThumbnail from Content_anime_class where mNameEN='" + ANIME_NAME.lower() + "';")
                        records = cursor.fetchall()
                        temp_str_thumbnail = None
                        for row in records:
                            temp_str_thumbnail = row[0]

                        if temp_str_thumbnail is None or temp_str_thumbnail == "" or temp_str_thumbnail == " ":
                            # Log and warn
                            print("Could not find a thumbnail for " + ANIME_NAME)
                            logging.warning("Could not find a thumbnail for " + ANIME_NAME)
                            continue

                        thumbnail_google_id = temp_str_thumbnail.strip().split("id=")[-1]

                        ANIME_FOLDER_ID = service.files().get(supportsAllDrives=True, fileId=thumbnail_google_id,
                                                              fields="parents").execute()

                        if ANIME_FOLDER_ID is None:
                            # Log and warn
                            print("There is no Google Drive folder for this anime " + ANIME_EPISODE_LINK)
                            logging.warning(
                                "There is no Google Drive folder for this anime " + ANIME_EPISODE_LINK)
                            break

                        # Get thumbnails folder ID
                        page_token = None
                        ANIME_THUMBNAILS_FOLDER_ID = None
                        while True:
                            google_drive_search_response = service.files().list(supportsAllDrives=True,
                                                                                includeItemsFromAllDrives=True,
                                                                                q="trashed = false and parents='" +
                                                                                  ANIME_FOLDER_ID["parents"][0] + "'",
                                                                                spaces='drive',
                                                                                fields='nextPageToken, files(id, name)',
                                                                                pageToken=page_token).execute()
                            for file in google_drive_search_response.get('files'):
                                if file['name'].strip().lower() == "thumbnails":
                                    ANIME_THUMBNAILS_FOLDER_ID = file.get('id')
                                    break

                            page_token = google_drive_search_response.get('nextPageToken', None)
                            if page_token is None:
                                break

                        if ANIME_THUMBNAILS_FOLDER_ID is None:
                            # Create thumbnails folder
                            file_metadata = {
                                'name': 'thumbnails',
                                'mimeType': 'application/vnd.google-apps.folder',
                                'parents': [ANIME_FOLDER_ID["parents"][0]]
                            }

                            anime_thumbnails_folder = service.files().create(body=file_metadata,
                                                                             supportsAllDrives=True).execute()
                            ANIME_THUMBNAILS_FOLDER_ID = anime_thumbnails_folder["id"]

                        if ANIME_EPISODE_IS_SPECIAL:
                            # Generate Episode Thumbnail
                            subprocess.call(['ffmpeg', '-y', '-i', TRUE_URL, '-ss', '00:05:00.000', '-vframes', '1',
                                             'temp/S' + str(ANIME_EPISODE_NUMBER) + '.jpg'])

                            # Upload a File
                            file_metadata = {
                                'name': "S" + str(ANIME_EPISODE_NUMBER) + '.jpg',
                                'parents': [ANIME_THUMBNAILS_FOLDER_ID]
                            }

                            media_content = MediaFileUpload('temp/S' + str(ANIME_EPISODE_NUMBER) + '.jpg',
                                                            mimetype='image/jpeg')
                        else:
                            # Generate Episode Thumbnail
                            subprocess.call(['ffmpeg', '-y', '-i', TRUE_URL, '-ss', '00:05:00.000', '-vframes', '1',
                                             'temp/' + str(ANIME_EPISODE_NUMBER) + '.jpg'])

                            # Upload a File
                            file_metadata = {
                                'name': "" + str(ANIME_EPISODE_NUMBER) + '.jpg',
                                'parents': [ANIME_THUMBNAILS_FOLDER_ID]
                            }

                            media_content = MediaFileUpload('temp/' + str(ANIME_EPISODE_NUMBER) + '.jpg',
                                                            mimetype='image/jpeg')

                        file = service.files().create(
                            body=file_metadata, media_body=media_content, supportsAllDrives=True).execute()

                        # Get sharable link
                        request_body = {
                            'role': 'reader',
                            'type': 'anyone'
                        }

                        response_permission = service.permissions().create(
                            fileId=file['id'], body=request_body, supportsAllDrives=True).execute()

                        response_share_link = service.files().get(
                            fileId=file['id'], fields='webViewLink', supportsAllDrives=True).execute()

                        ANIME_EPISODE_THUMBNAIL_IMAGE = "https://drive.google.com/uc?export=download&id=" + \
                                                        response_share_link["webViewLink"].rsplit('/', 2)[-2]
                    except ZeroDivisionError as ex:
                        print(ex)
                        ANIME_EPISODE_THUMBNAIL_IMAGE = ''
                        ANIME_EPISODE_DURATION = str(0)
                        print("Couldnt fetch " + ANIME_NAME + " episode " + str(
                            ANIME_EPISODE_NUMBER) + " skipping for now - " + TRUE_URL)
                        logging.critical("Couldnt fetch " + ANIME_NAME + " episode " + str(
                            ANIME_EPISODE_NUMBER) + " skipping for now - " + TRUE_URL)
                except Exception as ex:
                    print(ex)
                    ANIME_EPISODE_THUMBNAIL_IMAGE = ''
                    ANIME_EPISODE_DURATION = str(0)
                    print("Couldnt fetch " + ANIME_NAME + " episode " + str(
                        ANIME_EPISODE_NUMBER) + " skipping for now")
                    logging.critical("Couldnt fetch " + ANIME_NAME + " episode " + str(
                        ANIME_EPISODE_NUMBER) + " skipping for now")

                # Add to DB
                cursor.execute(
                    "insert into Content_episode_class values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                    (None, ANIME_EPISODE_NUMBER, ANIME_EPISODE_TITLE, None, ANIME_EPISODE_DURATION, 0,
                     ANIME_EPISODE_RELEASE_DATE, ANIME_EPISODE_THUMBNAIL_IMAGE, ANIME_NAME.lower(),
                     ANIME_EPISODE_VIDEO_URL, ANIME_EPISODE_IS_VCDN, ANIME_EPISODE_IS_SPECIAL))
                DB.commit()

                print("Anime " + ANIME_NAME + " Episode " + str(ANIME_EPISODE_NUMBER) + "added successfully!")
                logging.info("Anime " + ANIME_NAME + " Episode " + str(ANIME_EPISODE_NUMBER) + "added successfully!")

            else:  # If there is no anime, check if the episode is the first

                # Check if its special
                episode_title_string_span = item.find("span", class_="latestep_title")

                if episode_title_string_span is None:
                    episode_title_string_span = item.find("span", class_="latestep_stitle")

                episode_title_string = episode_title_string_span.find("a")

                if episode_title_string.text.strip().split(" ")[-1].isdigit() == False:
                    if "." in episode_title_string.text.strip().split(" ")[-1]:
                        ep_title_compare_string = "Special"
                        temporary_episode_number = -1

                        anime_error_title = ''.join(
                            str(e + " ") for e in episode_title_string.text.strip().split(" ")[:-2])
                    else:
                        if episode_title_string.text.strip().split(" ")[-1].lower() == "final":
                            ep_title_compare_string = episode_title_string.text.strip().split(" ")[-3]
                            temporary_episode_number = int(episode_title_string.text.strip().split(" ")[-2])

                            anime_error_title = ''.join(
                                str(e + " ") for e in episode_title_string.text.strip().split(" ")[:-3])
                        else:
                            ep_title_compare_string = "Special"
                            temporary_episode_number = -1

                            anime_error_title = episode_title_string.text.strip()
                else:
                    ep_title_compare_string = episode_title_string.text.strip().split(" ")[-2]
                    temporary_episode_number = int(episode_title_string.text.strip().split(" ")[-1])

                    anime_error_title = ''.join(str(e + " ") for e in episode_title_string.text.strip().split(" ")[:-2])

                if ep_title_compare_string == "Episode":

                    if temporary_episode_number == 1:
                        anime_a_tag = item.find("a", class_="latest-parent")
                        readable_line = URL + anime_a_tag["href"]

                        # Remove last slash if there is any
                        readable_line = readable_line.strip()
                        if readable_line[-1] == '/':
                            readable_line = readable_line[:-1]

                        # Get request to the page
                        session = cloudscraper.create_scraper()
                        page = session.get(readable_line + "/", headers=headers)

                        if page.status_code != 200:
                            # Log and error
                            print("Got status code " + str(page.status_code) + " for " + readable_line)
                            logging.critical(
                                "Got status code " + str(page.status_code) + " for " + readable_line)
                            break

                        # Start bs4
                        soup = BeautifulSoup(page.content, "lxml")
                        anime_info = soup.find("div", class_="row animeinfo-div")

                        # Log the start of the scrape
                        print("Scrape started for " + readable_line.rsplit('/', 1)[-1])
                        logging.info("Scrape started for " + readable_line.rsplit('/', 1)[-1])

                        # Get anime name EN
                        anime_name_tag = anime_info.find('h2')
                        ANIME_NAME = anime_name_tag.b.text.strip().replace("'", "").replace("?", "")

                        # Get anime name JP
                        single_episode_info = soup.find('div', class_="well episode_well")

                        if single_episode_info is not None:
                            span_with_anime_name = single_episode_info.find('div', class_="anime-title")
                            split_anime_name = span_with_anime_name.text.strip().rsplit(" ", 2)[0]

                            if SequenceMatcher(None, ANIME_NAME.lower().strip(),
                                               split_anime_name.replace("?", "").lower().strip()).ratio() < 0.7:
                                ANIME_NAME_JP = split_anime_name.lower()
                            else:
                                ANIME_NAME_JP = None
                        else:
                            ANIME_NAME_JP = None

                        cursor.execute(
                            "select count(*) from Content_anime_class where mNameEN='" + ANIME_NAME.lower() + "';")
                        records = cursor.fetchall()
                        qtd = 0
                        for row in records:
                            qtd = row[0]

                        if qtd > 0:
                            # Log and error
                            print("Anime already in the database, skipping... ")
                            logging.info("Anime already in the database, skipping... ")
                            continue

                        # Get anime description
                        anime_description_div = anime_info.find('div', class_="visible-md visible-lg")
                        ANIME_DESCRIPTION = anime_description_div.text.strip().replace('Description:', '').strip()

                        # Get anime categories
                        anime_category_tags = anime_info.find_all('a', class_="animeinfo_label")
                        ANIME_CATEGORIES = []
                        for a in anime_category_tags:
                            ANIME_CATEGORIES.append(a.span.text.strip())

                        # Get anime thumbnail
                        anime_image_tag = anime_info.find('img', class_="lozad img-thumbnail img-responsive infoposter")
                        image_url = "https://anime-update.com" + anime_image_tag['data-src']
                        image_filename = image_url.split('/')[-1]

                        image_thumbnail_request = session.get(image_url, headers=headers, stream=True)
                        if image_thumbnail_request.status_code != 200:
                            # Log and error
                            print("Could not fetch anime thumbnail")
                            logging.critical("Could not fetch anime thumbnail")
                            exit()

                        image_thumbnail_request.raw.decode_content = True
                        if not os.path.exists('temp'):
                            os.makedirs('temp')

                        with open('temp/' + image_filename, 'wb') as f:
                            shutil.copyfileobj(image_thumbnail_request.raw, f)

                            print("Anime thumbnail image downloaded! Starting upload... ")
                            logging.info("Anime thumbnail image downloaded! Starting upload... ")

                            # Create anime folder
                            file_metadata = {
                                'name': ANIME_NAME.lower(),
                                'mimeType': 'application/vnd.google-apps.folder',
                                'parents': ['1_VVMd9SHkUDDB-M9JDL6M9Scs0lStghJ']
                            }

                            anime_folder = service.files().create(body=file_metadata, supportsAllDrives=True).execute()
                            ANIME_FOLDER_ID = anime_folder["id"]

                            # Create thumbnails folder
                            file_metadata = {
                                'name': 'thumbnails',
                                'mimeType': 'application/vnd.google-apps.folder',
                                'parents': [ANIME_FOLDER_ID]
                            }

                            anime_thumbnails_folder = service.files().create(body=file_metadata,
                                                                             supportsAllDrives=True).execute()
                            ANIME_THUMBNAILS_FOLDER_ID = anime_thumbnails_folder["id"]

                            # Upload File and get Link
                            file_metadata = {
                                'name': image_filename,
                                'parents': [ANIME_FOLDER_ID]
                            }

                            if image_filename.split('.')[-1] == 'jpg':
                                media_content = MediaFileUpload('temp/' + image_filename, mimetype='image/jpeg')
                            else:
                                media_content = MediaFileUpload('temp/' + image_filename, mimetype='image/png')

                            file = service.files().create(
                                body=file_metadata, media_body=media_content, supportsAllDrives=True).execute()

                            # Get sharable link
                            request_body = {
                                'role': 'reader',
                                'type': 'anyone'
                            }

                            response_permission = service.permissions().create(
                                fileId=file['id'], body=request_body, supportsAllDrives=True).execute()

                            response_share_link = service.files().get(
                                fileId=file['id'], fields='webViewLink', supportsAllDrives=True).execute()

                            ANIME_THUMBNAIL = "https://drive.google.com/uc?export=download&id=" + \
                                              response_share_link["webViewLink"].rsplit('/', 2)[-2]

                        # Get on going
                        anime_ongoing_tags = anime_info.find_all('p')
                        if anime_ongoing_tags[2].text.strip().find("Completed") != -1:
                            ANIME_ONGOING = False
                        else:
                            ANIME_ONGOING = True

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

                        print("Anime info added!")
                        logging.info("Anime info added!")

                        print("Fetching episodes...")
                        logging.info("Fetching episodes...")

                        EPISODES = []
                        # Read normal episodes
                        alternative_counter = 1
                        for ep_link in ANIME_EPISODE_LINKS:
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

                            # Episode Release Date
                            ANIME_EPISODE_RELEASE_DATE = ANIME_EPISODE_DATES[int(ANIME_EPISODE_NUMBER) - 1]

                            # Make Episode Request
                            episode_session = cloudscraper.create_scraper()
                            episode_page = episode_session.get(ep_link, headers=headers)

                            if episode_page.status_code != 200:
                                # Log and error
                                print(
                                    "Got status code " + str(episode_page.status_code) + " for " + ep_link)
                                logging.critical(
                                    "Got status code " + str(episode_page.status_code) + " for " + ep_link)
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
                                                vide_iframe_innerHTML = js_name_verifier[
                                                                        js_name_verifier.find("<iframe"):-3]
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

                                    vcdn_url = "https://vcdn2.space/api/source/" + \
                                               ANIME_EPISODE_VIDEO_URL.rsplit('/', 1)[-1]

                                    vcdn_payload = "r=&d=vcdn2.space"
                                    vcdn_headers = {
                                        'authority': 'vcdn2.space',
                                        'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
                                        'accept': '*/*',
                                        'x-requested-with': 'XMLHttpRequest',
                                        'sec-ch-ua-mobile': '?0',
                                        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
                                        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                        'origin': 'https://vcdn2.space',
                                        'sec-fetch-site': 'same-origin',
                                        'sec-fetch-mode': 'cors',
                                        'sec-fetch-dest': 'empty',
                                        'referer': ANIME_EPISODE_VIDEO_URL,
                                        'accept-language': 'en-US,en;q=0.9'
                                    }

                                    vcdn_response = requests.request("POST", vcdn_url, headers=vcdn_headers,
                                                                     data=vcdn_payload)
                                    vcdn_data = vcdn_response.json()

                                    vcdn_redirect_link = ''
                                    for d in vcdn_data['data']:
                                        vcdn_redirect_link = d['file']

                                    vcdn_r = requests.get(vcdn_redirect_link, stream=True, verify=False)

                                    TRUE_URL = vcdn_r.url

                                else:
                                    # Log and warn
                                    print("There is no VCDN player for " + ep_link + ", trying Video")
                                    logging.warning(
                                        "There is no VCDN player for " + ep_link + ", trying Video")

                                    episode_player = episode_player_wraper.find("div", {"id": "gstore"})

                                    if episode_player is None:
                                        break

                                    ANIME_EPISODE_IS_VCDN = False

                                    episode_player_js = episode_soup.find_all("script")
                                    for script in episode_player_js:

                                        function_check = script.string
                                        if function_check is None:
                                            continue

                                        strip_function_check = function_check.strip()

                                        if strip_function_check[0:8] == "function":
                                            js_name_verifier = strip_function_check[9:]

                                            if js_name_verifier[:js_name_verifier.find("()")] == 'gstore':
                                                video_src = js_name_verifier[
                                                            js_name_verifier.find("/redirect/"):js_name_verifier.find(
                                                                "', type: 'video/mp4'")]

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

                                    TRUE_URL = ANIME_EPISODE_VIDEO_URL

                                print("Calculating video length for " + TRUE_URL)
                                logging.info("Calculating video length for " + TRUE_URL)

                                try:
                                    video = cv2.VideoCapture(TRUE_URL)
                                    frames = video.get(cv2.CAP_PROP_FRAME_COUNT)
                                    fps = int(video.get(cv2.CAP_PROP_FPS))
                                    seconds = int(frames / fps)

                                    ANIME_EPISODE_DURATION = str(seconds)

                                    # Generate Episode Thumbnail
                                    subprocess.call(
                                        ['ffmpeg', '-y', '-i', TRUE_URL, '-ss', '00:05:00.000', '-vframes', '1',
                                         'temp/' + str(ANIME_EPISODE_NUMBER) + '.jpg'])

                                    # Upload a File
                                    file_metadata = {
                                        'name': str(ANIME_EPISODE_NUMBER) + '.jpg',
                                        'parents': [ANIME_THUMBNAILS_FOLDER_ID]
                                    }

                                    media_content = MediaFileUpload('temp/' + str(ANIME_EPISODE_NUMBER) + '.jpg',
                                                                    mimetype='image/jpeg')

                                    file = service.files().create(
                                        body=file_metadata, media_body=media_content, supportsAllDrives=True).execute()

                                    # Get sharable link
                                    request_body = {
                                        'role': 'reader',
                                        'type': 'anyone'
                                    }

                                    response_permission = service.permissions().create(
                                        fileId=file['id'], body=request_body, supportsAllDrives=True).execute()

                                    response_share_link = service.files().get(
                                        fileId=file['id'], fields='webViewLink', supportsAllDrives=True).execute()

                                    ANIME_EPISODE_THUMBNAIL_IMAGE = "https://drive.google.com/uc?export=download&id=" + \
                                                                    response_share_link["webViewLink"].rsplit('/', 2)[
                                                                        -2]
                                except ZeroDivisionError as ex:
                                    print(ex)
                                    ANIME_EPISODE_THUMBNAIL_IMAGE = ''
                                    ANIME_EPISODE_DURATION = str(0)
                                    print("Couldnt fetch " + ANIME_NAME + " episode " + str(
                                        ANIME_EPISODE_NUMBER) + " skipping for now - " + TRUE_URL)
                                    logging.critical("Couldnt fetch " + ANIME_NAME + " episode " + str(
                                        ANIME_EPISODE_NUMBER) + " skipping for now - " + TRUE_URL)
                            except Exception as ex:
                                print(ex)
                                ANIME_EPISODE_THUMBNAIL_IMAGE = ''
                                ANIME_EPISODE_DURATION = str(0)
                                print("Couldnt fetch " + ANIME_NAME + " episode " + str(
                                    ANIME_EPISODE_NUMBER) + " skipping for now - " + TRUE_URL)
                                logging.critical("Couldnt fetch " + ANIME_NAME + " episode " + str(
                                    ANIME_EPISODE_NUMBER) + " skipping for now - " + TRUE_URL)

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

                        # Add anime to DB
                        if ANIME_NAME_JP is not None:
                            cursor.execute("insert into Content_anime_class values (%s, %s, %s, %s, %s, %s);", (
                            ANIME_NAME.lower(), ANIME_NAME_JP.lower().strip(), ANIME_DESCRIPTION, ANIME_THUMBNAIL,
                            len(EPISODES), ANIME_ONGOING))
                        else:
                            cursor.execute("insert into Content_anime_class values (%s, %s, %s, %s, %s, %s);", (
                            ANIME_NAME.lower(), None, ANIME_DESCRIPTION, ANIME_THUMBNAIL, len(EPISODES), ANIME_ONGOING))
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
                            cursor.execute(
                                "insert into Content_episode_class values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                                (None, ep["mEpisodeNumber"], ep["mNameEN"], None, ep["mLengthSecs"], 0,
                                 ep["mReleaseDate"], ep["mThumbnail"], ANIME_NAME.lower(), ep["mVideoFileLink"],
                                 ep["mVCDN"], ep["mIsSpecial"]))
                            DB.commit()

                        print("Anime " + ANIME_NAME + " added successfully!")
                        logging.info("Anime " + ANIME_NAME + " added successfully!")

                    else:
                        print("Anime " + anime_error_title + "has not been added yet. Skipping...")
                        logging.info("Anime " + anime_error_title + "has not been added yet. Skipping...")
                        continue
                else:
                    print("Anime " + anime_error_title + "has not been added yet. Skipping...")
                    logging.info("Anime " + anime_error_title + "has not been added yet. Skipping...")
                    continue
    else:
        # Log and error
        print("Could now get any episode items")
        logging.critical("Could now get any episode items")
        exit()

    print("All new episodes added successfully! Checking back in an hour...")
    logging.info("All new episodes added successfully! Checking back in an hour...")
    time.sleep(3600)
