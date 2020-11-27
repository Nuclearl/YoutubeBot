import requests
from config import API_KEY1
from lxml import html

def check_quota(json_data):
    try:
        if json_data["errors"][0]["reason"] == "quotaExceeded":
            return True
    except:
        return False


def get_id_from_videoid(API_KEY, video_id):
    var = requests.get(f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={API_KEY}")
    if var.request == 403:
        if check_quota(var.json()):
            if API_KEY == API_KEY1:
                return False
            get_id_from_videoid(API_KEY1, video_id)
        else:
            return False
    try:
        channel_id = var.json()['items'][0]['snippet']['channelId']
    except:
        return False
    return channel_id


def get_id_from_user_id(API_KEY, user_id):
    var = requests.get(
        f"https://www.googleapis.com/youtube/v3/channels?key={API_KEY}&forUsername={user_id}&part=id")
    if var.request == 403:
        if check_quota(var.json()):
            if API_KEY == API_KEY1:
                return False
            get_id_from_user_id(API_KEY1, user_id)
        else:
            return False
    try:
        channel_id = var.json()['items'][0]['id']
    except:
        return False
    return channel_id


def get_video_by_channelID(API_KEY, channel_id):
    id = []
    var = requests.get(
        f"https://www.googleapis.com/youtube/v3/channels?id={channel_id}&key={API_KEY}&part=contentDetails")
    if var.request == 403:
        if check_quota(var.json()):
            if API_KEY == API_KEY1:
                return False
            get_video_by_channelID(API_KEY1, channel_id)
        else:
            return False
    try:
        playlists_id = var.json()['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    except:
        return False
    var = requests.get(
        f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet%2CcontentDetails&maxResults=49&playlistId={playlists_id}&key={API_KEY}")
    if var.request == 403:
        if check_quota(var.json()):
            if API_KEY == API_KEY1:
                return False
            get_video_by_channelID(API_KEY1, channel_id)
        else:
            return False
    try:
        for i in var.json()['items']:
            id.append(i['contentDetails']['videoId'])
    except:
        return False
    stream_video = get_live_stream(channel_id)
    if stream_video:
        id.append(stream_video)
    return id


def get_name_channel_by_id(API_KEY, channel_id):
    var = requests.get(
        f"https://www.googleapis.com/youtube/v3/channels?part=id%2Csnippet%2Cstatistics%2CcontentDetails%2CtopicDetails&id={channel_id}&key={API_KEY}")
    if var.request == 403:
        if check_quota(var.json()):
            if API_KEY == API_KEY1:
                return False
            get_name_channel_by_id(API_KEY1, channel_id)
        else:
            return False
    try:
        name = var.json()['items'][0]['snippet']['title']
    except:
        return False
    return name


def get_live_stream(channel_id):
    try:
        page = requests.get(f"https://www.youtube.com/embed/live_stream?channel={channel_id}")
        if page.status_code == 200:
            tree = html.fromstring(page.content)
            links = tree.xpath('//link[@rel="canonical"]')
            if links:
                return links[0].attrib['href'].split("watch?v=")[1]
            else:
                return False
        else:
            return False
    except:
        return False
