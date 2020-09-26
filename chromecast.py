import ssl
import time
import struct
import json
import re
import sys
from socket import *
from urllib import request, parse

import chromecast_pb2 # Build this with: protoc --python_out=./ chromecast.proto

APP_MEDIA_RECIEVER = 'CC1AD845' # Default media-player, eats anything more or less
APP_YOUTUBE = '233637DE' # Youtube specific player

SESSION = 'receiver-0' # The current session, reciever-0 is a default magic keyword for un-initialized content. Aka, "hey chromecast"
YOUTUBE_API_BIND_DATA = {"device": "REMOTE_CONTROL",
						"id": "aaaaaaaaaaaaaaaaaaaaaaaaaa",
						"name": "Python",
						"mdx-version": 3,
						"pairing_type": "cast",
						"app": "android-phone-13.14.55"}

SID_REGEX = '"c","(.*?)",\"'
GSESSION_ID_REGEX = '"S","(.*?)"]'
REQ_PREFIX = "req{req_id}"

CONNECT_URL = 'urn:x-cast:com.google.cast.tp.connection'
HEARTBEAT_URL = 'urn:x-cast:com.google.cast.tp.heartbeat'
YOUTUBE_URL = 'urn:x-cast:com.google.youtube.mdx'
RECEIVER_URL = 'urn:x-cast:com.google.cast.receiver'
#MEDIA_URL = 'urn:x-cast:com.google.cast.media'

COOKIE = None

context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

s = socket()
s.connect(('172.16.13.3', 8009))
ss = context.wrap_socket(s)

def send(sock, endpoint, data):
	frame = chromecast_pb2.CastMessage()
	frame.protocol_version = frame.ProtocolVersion.CASTV2_1_0
	frame.source_id = 'sender-0'
	frame.destination_id = SESSION
	frame.namespace = endpoint
	frame.payload_type = 0

	frame.payload_utf8 = json.dumps(data, ensure_ascii=False).encode("utf8")
	ss.send(struct.pack(">I", frame.ByteSize()) + frame.SerializeToString())

def _format_session_params(_req_count, param_dict):
	req_count = REQ_PREFIX.format(req_id=_req_count)
	return {req_count + k if k.startswith("_") else k: v for k, v in param_dict.items()}

send(ss, CONNECT_URL, {"type": "CONNECT"})
send(ss, RECEIVER_URL, {"type": "GET_STATUS"})
send(ss, RECEIVER_URL, {"type": "LAUNCH", "requestId": 1, "appId": APP_YOUTUBE})

while 1:
	message_length = struct.unpack('>I', ss.recv(4))[0]
	raw_message = ss.recv(message_length)

	message = chromecast_pb2.CastMessage()
	message.ParseFromString(raw_message)
	
	data = json.loads(message.payload_utf8)
	print('Recieved:', data)

	if 'type' in data and data['type'].lower() == 'ping':
		send(ss, HEARTBEAT_URL, {"type": "PONG"})
	elif 'type' in data and data['type'].lower() == 'receiver_status':
		if 'status' in data and 'applications' in data['status'] and data['status']['applications'][0]['appId'] == APP_YOUTUBE:
			## YouTube has launched.
			## We need to connect to that newly launched session.
			SESSION = data['status']['applications'][0]['sessionId']

			send(ss, CONNECT_URL, {"type": "CONNECT"}) # Connect with the new SESSION id
			send(ss, YOUTUBE_URL, {'type': 'getMdxSessionStatus'}) # Get the lounge ID

	elif 'type' in data and data['type'].lower() == 'mdxsessionstatus':
		## Get the lounge_id (screen_id) from the current YouTube session on the chromecast
		## We need this to insert video_id's into the lounge.
		SCREEN_ID = data['data']['screenId']
		DEVICE_ID = data['data']['deviceId']

		# Do a HTTPS post to the lounge API: https://github.com/ur1katz/casttube/blob/08021a0f15fcd1c34c286acc9b903e2e9174a89b/casttube/YouTubeSession.py
		data = parse.urlencode({"screen_ids": SCREEN_ID}).encode()
		req =  request.Request("https://www.youtube.com/api/lounge/pairing/get_lounge_token_batch", data=data)
		resp = request.urlopen(req)
		lounge_data = json.loads(resp.read().decode('UTF-8'))

		# Grab the lounge token so we have a key that allows
		# us to insert videos.
		LOUNGE_TOKEN = lounge_data['screens'][0]['loungeToken']

		params = parse.urlencode({'RID': 0, 'VER': 8, 'CVER': 1})
		headers = {'X-YouTube-LoungeId-Token' : LOUNGE_TOKEN}
		url = "https://www.youtube.com/api/lounge/bc/bind?%s" % params
		data = parse.urlencode(YOUTUBE_API_BIND_DATA).encode()
		req =  request.Request(url, data=data, headers=headers)
		resp = request.urlopen(req)
		bind_raw_data = resp.read().decode('UTF-8')
		for key, val in resp.getheaders():
			if key.lower() == 'set-cookie':
				print(val)
				COOKIE = val.split(';',1)[0].strip()

		sid = re.search(SID_REGEX, bind_raw_data)
		gsessionid = re.search(GSESSION_ID_REGEX, bind_raw_data)
		
		SID = sid.group(1)
		GSESSION_ID = gsessionid.group(1)

		print('Starting a video..')

		request_data = {"_listId": "",
						"__sc": "setPlaylist",
						"_currentTime": "0",
						"_currentIndex": -1,
						"_audioOnly": "false",
						"_videoId": sys.argv[1],
						"count": 1}
		url_params = {"SID": SID, "gsessionid": GSESSION_ID,
						"RID": 1, "VER": 8, "CVER": 1}
		request_data = _format_session_params(0, request_data)

		params = parse.urlencode(url_params)
		headers = {'X-YouTube-LoungeId-Token' : LOUNGE_TOKEN, 'Cookie' : COOKIE}
		url = "https://www.youtube.com/api/lounge/bc/bind?%s" % params
		data = parse.urlencode(request_data).encode()
		req =  request.Request(url, data=data, headers=headers)
		resp = request.urlopen(req)

		video_play_raw_data = resp.read().decode('UTF-8')
		
	time.sleep(0.5)