import datetime
import json
import os
import logging
import pathlib
import shutil
import subprocess
import time

import urllib.parse
from difflib import SequenceMatcher

import paramiko
import cv2
import requests

import cloudscraper
import mysql.connector

from bs4 import BeautifulSoup

# Global Variables
app_config = None
url = "https://anime-update.com"


# Methods
def get_new_episodes(headers):
    global url

    session = cloudscraper.create_scraper()
    page = session.get(url, headers=headers)

    if page.status_code != 200:
        # Log and error
        print("Got status code " + str(page.status_code) + " for " + url)
        logging.critical(
            "Got status code " + str(page.status_code) + " for " + url)
        exit()

    # Start bs4
    soup = BeautifulSoup(page.content, "lxml")
    anime_info = soup.find("div", {"id": "latest"})

    # Scrape episode items
    episode_items = anime_info.find_all("div", class_="latestep_wrapper")

    if episode_items is None:
        # Log and error
        print("Could not fetch any episodes to scrape.")
        logging.critical("Could not fetch any episodes to scrape.")
        exit()

    return episode_items


def get_episode_mp4(vcdn_url):
    vcdn_url = "https://vcdn2.space/api/source/" + vcdn_url.rsplit('/', 1)[-1]

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
        'referer': vcdn_url,
        'accept-language': 'en-US,en;q=0.9'
    }

    vcdn_response = requests.request("POST", vcdn_url, headers=vcdn_headers, data=vcdn_payload)
    vcdn_data = vcdn_response.json()

    vcdn_redirect_link = ''
    for d in vcdn_data['data']:
        vcdn_redirect_link = d['file']

    vcdn_r = requests.get(vcdn_redirect_link, stream=True, verify=False)

    return vcdn_r.url


def get_episode_length(mp4_url):
    video = cv2.VideoCapture(mp4_url)
    frames = video.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = int(video.get(cv2.CAP_PROP_FPS))
    seconds = int(frames / fps)

    return seconds


def sftp_exists(sftp, path):
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False


def generate_thumbnail(mp4_url, is_special, episode_number, anime_name):
    # Initiate SFTP
    transport = paramiko.Transport((app_config['sftp_host'], app_config['sftp_port']))
    transport.connect(username=app_config['sftp_username'], password=app_config['sftp_password'])
    sftp = paramiko.SFTPClient.from_transport(transport)

    if is_special:
        # Generate Episode Thumbnail
        subprocess.call(['ffmpeg', '-y', '-i', mp4_url, '-ss', '00:05:00.000', '-vframes', '1',
                         'temp/S' + str(episode_number) + '.jpg'])

        # Upload Thumbnail
        sftp.put(os.path.join(os.path.join(pathlib.Path().resolve(), 'temp'), 'S' + str(episode_number) + '.jpg'),
                 app_config['sftp_data_path'] + '/' + anime_name.lower() +
                 '/thumbnails/S' + str(episode_number) + '.jpg')
        sftp.close()
        transport.close()

        return app_config['media_host_url'] + urllib.parse.quote(anime_name.lower(), safe='') + \
               '/thumbnails/S' + str(episode_number) + '.jpg'
    else:
        # Generate Episode Thumbnail
        subprocess.call(['ffmpeg', '-y', '-i', mp4_url, '-ss', '00:05:00.000', '-vframes', '1',
                         'temp/' + str(episode_number) + '.jpg'])

        # Upload Thumbnail
        sftp.put(os.path.join(os.path.join(pathlib.Path().resolve(), 'temp'), str(episode_number) + '.jpg'),
                 app_config['sftp_data_path'] + '/' + anime_name.lower() +
                 '/thumbnails/' + str(episode_number) + '.jpg')
        sftp.close()
        transport.close()

        return app_config['media_host_url'] + urllib.parse.quote(anime_name.lower(), safe='') + \
               '/thumbnails/' + str(episode_number) + '.jpg'


def main():
    global app_config
    global url

    if app_config is None:
        print("Failed to import the config file.")
        logging.critical("Failed to import the config file.")
        exit()

    if 'user_agent' not in app_config or app_config['user_agent'] == '' or 'cloudflare_cookie' not in app_config or \
            app_config['cloudflare_cookie'] == '':
        print("User agent/Cloudflare Cookie not configured properly. Please check the config file!")
        logging.critical("User agent/Cloudflare Cookie not configured properly. Please check the config file!")
        exit()

    # Var Declaration
    headers = {
        'authority': 'anime-update.com',
        'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'sec-ch-ua-mobile': '?0',
        'user-agent': app_config['user_agent'],
        'cookie': app_config['cloudflare_cookie'],
        'sec-fetch-site': 'none',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-dest': 'document',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'accept-language': 'en-US,en;q=0.9',
        'accept-encoding': 'gzip, deflate'
    }

    db = mysql.connector.connect(host=app_config['db_host'],
                                 port=app_config['db_port'],
                                 database=app_config['db_database'],
                                 user=app_config['db_user'],
                                 password=app_config['db_password'])

    # Start App Cycle
    while True:
        # Check DB connection status
        if not db.is_connected():
            print("Could not connect to the database. Please check the config file!")
            logging.critical("Could not connect to the database. Please check the config file!")
            exit()

        # Get new episodes
        items = get_new_episodes(headers)

        anime_obj = {}
        for item in items:
            # Check for temp folder
            if not os.path.exists('temp'):
                os.makedirs('temp')

            # Check if the anime is in the DB
            span_anime_title = item.find("a", class_="latest-parent")
            anime_obj['name'] = span_anime_title["title"].strip().replace("'", "").replace("?", "")

            # Make the Query
            cursor = db.cursor()
            cursor.execute(
                "select count(*) from Content_anime_class where mNameEN='" + anime_obj['name'].lower() + "';")
            records = cursor.fetchall()
            qtd = 0
            for row in records:
                qtd = row[0]

            if qtd > 0:  # If there is an anime, then add the new episode
                episode = {}

                # Check if its special
                title_span = item.find("span", class_="latestep_title")
                if title_span is None:
                    title_span = item.find("span", class_="latestep_stitle")

                episode_title_string = title_span.find("a")
                episode_url = url + episode_title_string["href"]

                # Check if last character is not a digit
                if not episode_title_string.text.strip().split(" ")[-1].isdigit():
                    title_compare = episode_title_string.text.strip().split(" ")[-3]
                else:
                    title_compare = episode_title_string.text.strip().split(" ")[-2]

                if title_compare.lower() == 'episode':
                    episode['is_special'] = False
                else:
                    episode['is_special'] = True

                # Get Episode Number
                if episode_title_string.text.strip().split(" ")[-2].isdigit():
                    episode['episode_number'] = int(episode_title_string.text.strip().split(" ")[-2])
                elif episode_title_string.text.strip().split(" ")[-1].isdigit():
                    episode['episode_number'] = int(episode_title_string.text.strip().split(" ")[-1])
                else:
                    # Get number from DB
                    cursor = db.cursor()
                    cursor.execute("select count(*) from Content_episode_class where mAnime_id='" +
                                   anime_obj['name'].lower() + "' and mIsSpecial='" + str(episode['is_special']) + "';")
                    records = cursor.fetchall()
                    qtd = 0
                    for row in records:
                        qtd = row[0]

                    if qtd > 0:
                        episode['episode_number'] = qtd
                    else:
                        episode['episode_number'] = 1

                # Check if the episode already exists
                cursor = db.cursor()
                if episode['is_special']:
                    cursor.execute("select count(*) from Content_episode_class where mAnime_id='" +
                                   anime_obj['name'].lower() + "' and mIsSpecial=1 and mEpisodeNumber='" +
                                   str(episode['episode_number']) + "';")
                else:
                    cursor.execute("select count(*) from Content_episode_class where mAnime_id='" +
                                   anime_obj['name'].lower() + "' and mIsSpecial=0 and mEpisodeNumber='" +
                                   str(episode['episode_number']) + "';")
                records = cursor.fetchall()
                qtd = 0
                for row in records:
                    qtd = row[0]

                if qtd > 0:
                    # Log and error
                    print("Episode already exists, skipping... - ")
                    logging.warning("Episode already exists, skipping... - ")
                    continue

                # Get release date
                release_date_span = item.find("span", class_="label label-latestep label-timeago")
                if "day" not in release_date_span.text.strip().lower():
                    d = datetime.datetime.today() - datetime.timedelta(
                        hours=int(release_date_span.text.strip().split(" ")[0]))
                else:
                    d = datetime.datetime.today() - datetime.timedelta(
                        days=int(release_date_span.text.strip().split(" ")[0]))

                episode['release_date'] = d.strftime("%Y") + "-" + d.strftime("%m") + "-" + d.strftime("%d") + " " + \
                                          d.strftime("%H") + ":" + d.strftime("%m") + ":00.000000"

                # Make Episode Request
                episode_session = cloudscraper.create_scraper()
                episode_page = episode_session.get(episode_url, headers=headers)

                if episode_page.status_code != 200:
                    # Log and error
                    print("Got status code " + str(episode_page.status_code) + " for " + episode_url)
                    logging.critical("Got status code " + str(episode_page.status_code) + " for " + episode_url)
                    exit()

                # Start bs4
                episode_soup = BeautifulSoup(episode_page.content, "lxml")

                # Get episode name
                episode_info = episode_soup.find("table", class_="episode_title_table hidden-xs")
                title_info = episode_info.find("h4")
                episode['nameEN'] = title_info.text.strip()
                episode['nameJP'] = None

                # Get episode video link
                episode_player_wraper = episode_soup.find("div", {"id": "videocontent"})
                episode_player = episode_player_wraper.find("div", {"id": "fembed"})

                if episode_player is not None:
                    episode['is_vcdn'] = True

                    # Get VCDN URL
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

                                episode['video_url'] = true_url_page.url

                                if episode['video_url'][-1] == '/':
                                    episode['video_url'] = episode['video_url'][:-1]

                                # Get MP4
                                mp4_url = get_episode_mp4(episode['video_url'])

                                # Get Video Length
                                try:
                                    print("Fetching video length for " + episode['nameEN'] + " - " + anime_obj['name'])
                                    logging.info(
                                        "Fetching video length for " + episode['nameEN'] + " - " + anime_obj['name'])
                                    episode['length_secs'] = get_episode_length(mp4_url)
                                except Exception as a:
                                    print(a)
                                    episode['length_secs'] = 0
                                    print("Could not fetch video lendth for " + episode['nameEN'] + ". Skipping...")
                                    logging.warning("Could not fetch video lendth for " + episode['nameEN']
                                                    + ". Skipping...")

                                # Generate Thumbnail
                                try:
                                    episode['thumbnail'] = generate_thumbnail(mp4_url, episode['is_special'],
                                                                              episode['episode_number'], anime_obj['name'])
                                except Exception as a:
                                    print(a)
                                    episode['thumbnail'] = ""
                                    print("Could not fetch thumbnail for " + episode['nameEN'] + ". Skipping...")
                                    logging.warning("Could not fetch thumbnail for " + episode['nameEN']
                                                    + ". Skipping...")
                            else:
                                continue
                        else:
                            continue
                else:
                    # Log and warn
                    print("There is no VCDN player for " + episode_url)
                    logging.warning("There is no VCDN player for " + episode_url)

                    episode['is_vcdn'] = False
                    episode['video_url'] = ""
                    episode['thumbnail'] = ""
                    episode['length_secs'] = 0

                # Add to DB
                cursor = db.cursor()
                cursor.execute(
                    "insert into Content_episode_class values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                    (None, episode['episode_number'], episode['nameEN'], episode['nameJP'], episode['length_secs'], 0,
                     episode['release_date'], episode['thumbnail'], anime_obj['name'].lower(),
                     episode['video_url'], episode['is_vcdn'], episode['is_special']))
                db.commit()

                print("Anime " + anime_obj['name'] + " Episode " + str(episode['episode_number']) + " added successfully!")
                logging.info(
                    "Anime " + anime_obj['name'] + " Episode " + str(episode['episode_number']) + " added successfully!")
            else:  # If the Anime does not exist, add it

                # Get Anime URL
                anime_a_tag = item.find("a", class_="latest-parent")
                anime_url = url + anime_a_tag["href"]

                # Remove last slash if there is any
                anime_url = anime_url.strip()
                if anime_url[-1] == '/':
                    anime_url = anime_url[:-1]

                # Request the page
                session = cloudscraper.create_scraper()
                page = session.get(anime_url + "/", headers=headers)

                if page.status_code != 200:
                    # Log and error
                    print("Got status code " + str(page.status_code) + " for " + anime_url)
                    logging.critical(
                        "Got status code " + str(page.status_code) + " for " + anime_url)
                    continue

                # Start bs4
                soup = BeautifulSoup(page.content, "lxml")
                anime_info = soup.find("div", class_="row animeinfo-div")

                # Log the start of the scrape
                print("Scrape started for " + anime_url.rsplit('/', 1)[-1])
                logging.info("Scrape started for " + anime_url.rsplit('/', 1)[-1])

                # Get anime name EN
                anime_name_tag = anime_info.find('h2')
                anime_obj['nameEN'] = anime_name_tag.b.text.replace("'", "").replace("?", "")

                # Get anime name JP
                single_episode_info = soup.find('div', class_="well episode_well")
                if single_episode_info is None:
                    single_episode_info = soup.find('div', class_="well special_well")

                if single_episode_info is not None:
                    span_with_anime_name = single_episode_info.find('div', class_="anime-title")
                    split_anime_name = span_with_anime_name.text.rsplit(" ", 2)[0]

                    if SequenceMatcher(None, anime_obj['nameEN'].lower().strip(),
                                       split_anime_name.replace("?", "").lower().strip()).ratio() < 0.7:
                        anime_obj['nameJP'] = split_anime_name.lower()
                    else:
                        anime_obj['nameJP'] = None
                else:
                    anime_obj['nameJP'] = None

                # Get anime description
                anime_description_div = anime_info.find('div', class_="visible-md visible-lg")
                anime_obj['description'] = anime_description_div.text.replace('Description:', '').strip()

                # Get anime categories
                anime_category_tags = anime_info.find_all('a', class_="animeinfo_label")
                anime_obj['categories'] = []
                for a in anime_category_tags:
                    anime_obj['categories'].append(a.span.text.strip())

                # Get anime thumbnail
                anime_image_tag = anime_info.find('img', class_="lozad img-thumbnail img-responsive infoposter")
                image_url = url + anime_image_tag['data-src']
                image_filename = image_url.split('/')[-1]

                image_thumbnail_request = session.get(image_url, headers=headers, stream=True)
                if image_thumbnail_request.status_code != 200:
                    anime_obj['thumbnail'] = ''

                    # Log and error
                    print("Could not fetch anime thumbnail")
                    logging.critical("Could not fetch anime thumbnail")
                    continue

                image_thumbnail_request.raw.decode_content = True
                if not os.path.exists('temp'):
                    os.makedirs('temp')

                with open('temp/' + image_filename, 'wb') as anime_thumbnail:
                    shutil.copyfileobj(image_thumbnail_request.raw, anime_thumbnail)

                    print("Anime thumbnail image downloaded! Starting upload...")
                    logging.info("Anime thumbnail image downloaded! Starting upload...")

                    # Create anime folder
                    transport = paramiko.Transport((app_config['sftp_host'], app_config['sftp_port']))
                    transport.connect(username=app_config['sftp_username'], password=app_config['sftp_password'])
                    sftp = paramiko.SFTPClient.from_transport(transport)

                    try:
                        sftp.mkdir(app_config['sftp_data_path'] + '/' + anime_obj['nameEN'].lower())
                    except OSError:
                        print("Got OS error on anime folder creation. Perhaps it already exists!")
                        logging.info("Got OS error on anime folder creation. Perhaps it already exists!")

                    # Create thumbnails folder
                    try:
                        sftp.mkdir(app_config['sftp_data_path'] + '/' + anime_obj['nameEN'].lower() + '/thumbnails')
                    except OSError:
                        print("Got OS error on thumbnails folder creation. Perhaps it already exists!")
                        logging.info("Got OS error on thumbnails folder creation. Perhaps it already exists!")

                    # Upload File and get Link
                    sftp.put('temp/' + image_filename, app_config['sftp_data_path'] + '/' + anime_obj['nameEN'].lower()
                             + '/' + image_filename)

                    # Get link and close connection
                    anime_obj['thumbnail'] = app_config['media_host_url'] + urllib.parse.quote(
                        anime_obj['nameEN'].lower(), safe='') + '/' + image_filename

                    sftp.close()
                    transport.close()
                    anime_thumbnail.close()

                # Get on going
                anime_ongoing_tags = anime_info.find_all('p')
                if anime_ongoing_tags[2].text.find("Completed") != -1:
                    anime_obj['on_going'] = False
                else:
                    anime_obj['on_going'] = True

                print("Anime info added!")
                logging.info("Anime info added!")

                print("Fetching episodes...")
                logging.info("Fetching episodes...")

                # Get the normal episodes
                anime_obj['episodes'] = []

                anime_tabcontent_div = soup.find("div", {"id": "eps"})
                anime_episode_div = anime_tabcontent_div.find("div", class_="col-sm-6")
                anime_episode_tags = anime_episode_div.find_all("a", class_="episode_well_link")
                for a in anime_episode_tags:
                    episode = {'is_special': False}

                    # Get episode URL
                    ep_link = "https://anime-update.com" + a['href']

                    # Get episode Date
                    span = a.find("span", class_="label pull-right animeupdate-color")
                    date = span.text.strip().split(" ")
                    # Make sure the day has 2 digits
                    day = str(date[0])
                    day = day.zfill(2)

                    if date[1] == "January":
                        episode['release_date'] = date[2] + "-01-" + day + " 00:00:00.000000"
                    elif date[1] == "February":
                        episode['release_date'] = date[2] + "-02-" + day + " 00:00:00.000000"
                    elif date[1] == "March":
                        episode['release_date'] = date[2] + "-03-" + day + " 00:00:00.000000"
                    elif date[1] == "April":
                        episode['release_date'] = date[2] + "-04-" + day + " 00:00:00.000000"
                    elif date[1] == "May":
                        episode['release_date'] = date[2] + "-05-" + day + " 00:00:00.000000"
                    elif date[1] == "June":
                        episode['release_date'] = date[2] + "-06-" + day + " 00:00:00.000000"
                    elif date[1] == "July":
                        episode['release_date'] = date[2] + "-07-" + day + " 00:00:00.000000"
                    elif date[1] == "August":
                        episode['release_date'] = date[2] + "-08-" + day + " 00:00:00.000000"
                    elif date[1] == "September":
                        episode['release_date'] = date[2] + "-09-" + day + " 00:00:00.000000"
                    elif date[1] == "October":
                        episode['release_date'] = date[2] + "-10-" + day + " 00:00:00.000000"
                    elif date[1] == "November":
                        episode['release_date'] = date[2] + "-11-" + day + " 00:00:00.000000"
                    elif date[1] == "December":
                        episode['release_date'] = date[2] + "-12-" + day + " 00:00:00.000000"

                    # Get episode number from URL
                    episode_denominator = ep_link[:-1].rsplit('/', 1)[-1]
                    split_denominator = episode_denominator.split("-")
                    if split_denominator[-1].isdigit():
                        episode['episode_number'] = int(split_denominator[-1])
                    else:
                        episode['episode_number'] = len(anime_obj['episodes']) + 1

                    # Make Episode Request
                    episode_session = cloudscraper.create_scraper()
                    episode_page = episode_session.get(ep_link, headers=headers)

                    if episode_page.status_code != 200:
                        episode['nameEN'] = ''
                        episode['nameJP'] = None
                        episode['length_secs'] = 0
                        episode['thumbnail'] = ''
                        episode['is_vcdn'] = False
                        episode['video_url'] = ''

                        anime_obj['episodes'].append(episode)
                        # Log and error
                        print("Got status code " + str(episode_page.status_code) + " for " + ep_link + ". Skipping...")
                        logging.critical("Got status code " + str(episode_page.status_code) + " for " + ep_link +
                                         ". Skipping...")

                        continue

                    # Start bs4
                    episode_soup = BeautifulSoup(episode_page.content, "lxml")

                    # Episode name
                    episode_info = episode_soup.find("table", class_="episode_title_table hidden-xs")
                    title_info = episode_info.find("h4")
                    episode['nameEN'] = title_info.text.strip()
                    episode['nameJP'] = None

                    # Get episode video link
                    episode_player_wraper = episode_soup.find("div", {"id": "videocontent"})
                    episode_player = episode_player_wraper.find("div", {"id": "fembed"})

                    if episode_player is not None:
                        episode['is_vcdn'] = True

                        # Get VCDN URL
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

                                    episode['video_url'] = true_url_page.url

                                    if episode['video_url'][-1] == '/':
                                        episode['video_url'] = episode['video_url'][:-1]

                                    # Get MP4
                                    mp4_url = get_episode_mp4(episode['video_url'])

                                    # Get Video Length
                                    try:
                                        print("Fetching video length for " + episode['nameEN'] + " - " + anime_obj[
                                            'name'])
                                        logging.info(
                                            "Fetching video length for " + episode['nameEN'] + " - " + anime_obj[
                                                'name'])
                                        episode['length_secs'] = get_episode_length(mp4_url)
                                    except Exception as a:
                                        print(a)
                                        episode['length_secs'] = 0
                                        print("Could not fetch video lendth for " + episode['nameEN'] + ". Skipping...")
                                        logging.warning("Could not fetch video lendth for " + episode['nameEN']
                                                        + ". Skipping...")

                                    # Generate Thumbnail
                                    try:
                                        episode['thumbnail'] = generate_thumbnail(mp4_url, episode['is_special'],
                                                                                  episode['episode_number'],
                                                                                  anime_obj['nameEN'])
                                    except Exception as a:
                                        print(a)
                                        episode['thumbnail'] = ""
                                        print("Could not fetch thumbnail for " + episode['nameEN'] + ". Skipping...")
                                        logging.warning("Could not fetch thumbnail for " + episode['nameEN']
                                                        + ". Skipping...")
                                else:
                                    continue
                            else:
                                continue
                    else:
                        # Log and warn
                        print("There is no VCDN player for " + episode_url)
                        logging.warning("There is no VCDN player for " + episode_url)

                        episode['is_vcdn'] = False
                        episode['video_url'] = ""
                        episode['thumbnail'] = ""
                        episode['length_secs'] = 0

                    anime_obj['episodes'].append(episode)

                # Get special episodes
                anime_tabcontent_div = soup.find("div", {"id": "specials"})
                if anime_tabcontent_div is not None:  # Check if there are any specials
                    anime_episode_tags = anime_tabcontent_div.find_all("a")

                    for a in anime_episode_tags:
                        episode = {'is_special': True}

                        # Get episode URL
                        ep_link = "https://anime-update.com" + a['href']

                        # Get episode date
                        span = a.find("span", class_="label pull-right animeupdate-color front_time")
                        date = span.text.strip().split(" ")
                        # Make sure the day has 2 digits
                        day = str(date[0])
                        day = day.zfill(2)

                        if date[1] == "January":
                            episode['release_date'] = date[2] + "-01-" + day + " 00:00:00.000000"
                        elif date[1] == "February":
                            episode['release_date'] = date[2] + "-02-" + day + " 00:00:00.000000"
                        elif date[1] == "March":
                            episode['release_date'] = date[2] + "-03-" + day + " 00:00:00.000000"
                        elif date[1] == "April":
                            episode['release_date'] = date[2] + "-04-" + day + " 00:00:00.000000"
                        elif date[1] == "May":
                            episode['release_date'] = date[2] + "-05-" + day + " 00:00:00.000000"
                        elif date[1] == "June":
                            episode['release_date'] = date[2] + "-06-" + day + " 00:00:00.000000"
                        elif date[1] == "July":
                            episode['release_date'] = date[2] + "-07-" + day + " 00:00:00.000000"
                        elif date[1] == "August":
                            episode['release_date'] = date[2] + "-08-" + day + " 00:00:00.000000"
                        elif date[1] == "September":
                            episode['release_date'] = date[2] + "-09-" + day + " 00:00:00.000000"
                        elif date[1] == "October":
                            episode['release_date'] = date[2] + "-10-" + day + " 00:00:00.000000"
                        elif date[1] == "November":
                            episode['release_date'] = date[2] + "-11-" + day + " 00:00:00.000000"
                        elif date[1] == "December":
                            episode['release_date'] = date[2] + "-12-" + day + " 00:00:00.000000"

                        # Episode number
                        episode_denominator = ep_link[:-1].rsplit('/', 1)[-1]
                        split_denominator = episode_denominator.split("-")
                        if split_denominator[-1].isdigit():
                            episode['episode_number'] = int(split_denominator[-1])
                        else:
                            qtd = 0
                            for ep_in_list in anime_obj['episodes']:
                                if ep_in_list['is_special']:
                                    qtd += 1

                            if qtd > 0:
                                episode['episode_number'] = qtd + 1
                            else:
                                episode['episode_number'] = 1

                        # Make Episode Request
                        episode_session = cloudscraper.create_scraper()
                        episode_page = episode_session.get(ep_link, headers=headers)

                        if episode_page.status_code != 200:
                            episode['nameEN'] = ''
                            episode['nameJP'] = None
                            episode['length_secs'] = 0
                            episode['thumbnail'] = ''
                            episode['is_vcdn'] = False
                            episode['video_url'] = ''
                            anime_obj['episodes'].append(episode)

                            # Log and error
                            print("Got status code " + str(
                                episode_page.status_code) + " for " + ep_link + ". Skipping...")
                            logging.critical(
                                "Got status code " + str(episode_page.status_code) + " for " + ep_link +
                                ". Skipping...")
                            continue

                        # Start bs4
                        episode_soup = BeautifulSoup(episode_page.content, "lxml")

                        # Episode name
                        episode_info = episode_soup.find("table", class_="episode_title_table hidden-xs")
                        title_info = episode_info.find("h4")
                        episode['nameEN'] = title_info.text.strip()
                        episode['nameJP'] = None

                        # Get episode video link
                        episode_player_wraper = episode_soup.find("div", {"id": "videocontent"})
                        episode_player = episode_player_wraper.find("div", {"id": "fembed"})

                        if episode_player is not None:
                            episode['is_vcdn'] = True

                            # Get VCDN URL
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

                                        episode['video_url'] = true_url_page.url

                                        if episode['video_url'][-1] == '/':
                                            episode['video_url'] = episode['video_url'][:-1]

                                        # Get MP4
                                        mp4_url = get_episode_mp4(episode['video_url'])

                                        # Get Video Length
                                        try:
                                            print("Fetching video length for " + episode['nameEN'] + " - " +
                                                  anime_obj['name'])
                                            logging.info(
                                                "Fetching video length for " + episode['nameEN'] + " - " +
                                                anime_obj['name'])
                                            episode['length_secs'] = get_episode_length(mp4_url)
                                        except Exception as a:
                                            print(a)
                                            episode['length_secs'] = 0
                                            print("Could not fetch video lendth for " + episode[
                                                'nameEN'] + ". Skipping...")
                                            logging.warning("Could not fetch video lendth for " + episode['nameEN']
                                                            + ". Skipping...")

                                        # Generate Thumbnail
                                        try:
                                            episode['thumbnail'] = generate_thumbnail(mp4_url,
                                                                                      episode['is_special'],
                                                                                      episode['episode_number'],
                                                                                      anime_obj['nameEN'])
                                        except Exception as a:
                                            print(a)
                                            episode['thumbnail'] = ""
                                            print("Could not fetch thumbnail for " + episode[
                                                'nameEN'] + ". Skipping...")
                                            logging.warning("Could not fetch thumbnail for " + episode['nameEN']
                                                            + ". Skipping...")
                                    else:
                                        continue
                                else:
                                    continue
                        else:
                            # Log and warn
                            print("There is no VCDN player for " + episode_url)
                            logging.warning("There is no VCDN player for " + episode_url)

                            episode['is_vcdn'] = False
                            episode['video_url'] = ""
                            episode['thumbnail'] = ""
                            episode['length_secs'] = 0

                        anime_obj['episodes'].append(episode)

                # Add anime to DB
                cursor = db.cursor()
                if anime_obj['nameJP'] is not None and anime_obj['nameJP'] != "" and anime_obj['nameJP'] != " ":
                    cursor.execute("insert into Content_anime_class values (%s, %s, %s, %s, %s, %s);",
                                   (anime_obj['nameEN'].lower(), anime_obj['nameJP'].lower().strip(),
                                    anime_obj['description'], anime_obj['thumbnail'], len(anime_obj['episodes']),
                                    anime_obj['on_going']))
                else:
                    cursor.execute("insert into Content_anime_class values (%s, %s, %s, %s, %s, %s);",
                                   (anime_obj['nameEN'].lower(), None, anime_obj['description'], anime_obj['thumbnail'],
                                    len(anime_obj['episodes']), anime_obj['on_going']))

                db.commit()

                # Add anime categories to DB
                for genre in anime_obj['categories']:
                    cursor.execute("insert into Content_anime_class_mCategories values(%s, %s, %s);",
                                   (None, anime_obj['nameEN'].lower(), genre.lower()))
                    db.commit()

                    cursor.execute(
                        "update Content_category_class set mAnimeCount=mAnimeCount+1 where mCategoryName='" + genre.lower() + "'")
                    db.commit()

                # Add episodes to DB
                for ep in anime_obj['episodes']:
                    # Add to DB
                    cursor.execute(
                        "insert into Content_episode_class values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);",
                        (None, ep['episode_number'], ep["nameEN"], ep["nameJP"], ep['length_secs'], 0,
                         ep['release_date'], ep['thumbnail'], anime_obj['nameEN'].lower(), ep['video_url'],
                         ep['is_vcdn'], ep["is_special"]))
                    db.commit()

                print("Anime " + anime_obj['nameEN'] + " added successfully!")
                logging.info("Anime " + anime_obj['nameEN'] + " added successfully!")

            print("Removing temp files...")
            logging.info("Removing temp files...")
            shutil.rmtree('temp')

        print("All new episodes added successfully! Checking back in half an hour...")
        logging.info("All new episodes added successfully! Checking back in half an hour...")
        time.sleep(1800)


if __name__ == '__main__':
    # Setup Logs
    if not os.path.exists('logs'):
        os.makedirs('logs')
    logging.basicConfig(filename="logs/" + str(datetime.datetime.now().year) + "-" + str(datetime.datetime.now().month)
                                 + "-" + str(datetime.datetime.now().day) + ".txt", format='%(asctime)s %(message)s',
                        filemode='w')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Setup Temp Folder
    if not os.path.exists('temp'):
        os.makedirs('temp')

    # Fetch Config
    if not os.path.exists('config/config.json'):

        # Create blank file and exit
        if not os.path.exists('config'):
            os.makedirs('config')
        with open("config/config.json", "w") as config_file:
            blank_config = {
                "cloudflare_cookie": "",
                "user_agent": "",
                "media_host_url": "https://animewatcher-media.bagsplusportugal.com/",
                "db_host": "",
                "db_port": 3306,
                "db_database": "",
                "db_user": "",
                "db_password": "",
                "sftp_data_path": "",
                "sftp_host": "",
                "sftp_port": -1,
                "sftp_username": "",
                "sftp_password": ""
            }
            obj = json.dumps(blank_config, indent=4)

            config_file.write(obj)
            config_file.close()

        print("Config file not found. A blank one has been created, please fill it out first!")
        logging.critical("Config file not found. A blank one has been created, please fill it out first!")
        exit()
    else:
        # Import configuration
        with open('config/config.json', 'r') as f:
            app_config = json.load(f)
            f.close()

        # Correct data_path and url syntax if needed
        if app_config['media_host_url'][-1] != '/':
            app_config['media_host_url'] += '/'

        if app_config['sftp_data_path'][-1] == '/':
            app_config['sftp_data_path'] = app_config['sftp_data_path'][:-1]

    # Start main program
    main()
