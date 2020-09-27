import ssl
import time
import struct
import json
import re
import sys
import urllib.request
import urllib.parse
from socket import *
#from urllib import request, parse
from collections import OrderedDict

CHROMECAST_IP = sys.argv[1]
VIDEO_ID = sys.argv[2]

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
GENERIC_MEDIA_URL = 'urn:x-cast:com.google.cast.media'

if 'http' in VIDEO_ID and 'youtu.be' not in VIDEO_ID and not 'youtube.com' in VIDEO_ID:
	print('Setting up Default Media app for launch.')
	LAUNCH_APP = APP_MEDIA_RECIEVER
else:
	print('Setting up YouTube for launch.')
	LAUNCH_APP = APP_YOUTUBE

COOKIE = None

context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

s = socket()
s.connect((CHROMECAST_IP, 8009))
ss = context.wrap_socket(s)

def varint(number):
	# Source: https://github.com/fmoo/python-varint/blob/99b4d9262a0f1b46fad3b3bf60c7a15e7a031df2/varint.py#L26-L37
	"""Pack `number` into varint bytes"""
	buf = b''
	while True:
		towrite = number & 0x7f
		number >>= 7
		if number:
			buf += bytes((towrite | 0x80, ))
		else:
			buf += bytes((towrite, ))
			break
	return buf

def json_to_protobuf(data):
	"""
	Extremely simplified JSON -> ProtoBuf serializer.

	src: https://developers.google.com/protocol-buffers/docs/encoding

	Variable type overview:
	| 0 | Integer |
	| 2 | Length  | UTF-8 string |

	If the length's first bit (10000000) is a ONE (1),
	It means the length is greater than 127 and we need one more byte for the length,
	as well as do some magic on the length (flip the order, remove MSB etc)
	"""
	# https://developers.google.com/protocol-buffers/docs/encoding
	if type(data) != dict: data = json.loads(data)
	sequence = list(data.items())

	serialized = b''
	for index, (key, val) in enumerate(sequence):
		MSB = 0b00000000
		#if len(sequence) == index+1:
		#	MSB = 0b10000000

		field_number = index + 1 << 3
		if type(val) is int:
			wire_type = 0b00000000

			segment = struct.pack('B', val)
		elif type(val) is str:
			wire_type = 0b00000010

			segment = varint(len(val)) + bytes(val, 'UTF-8')

		serialized += struct.pack('B', MSB|field_number|wire_type) + segment

	# The length is not actually part of the ProtoBuf format,
	# But since this function is souly used to send data,
	# we include the leangth here so we don't have to deal with
	# it on every packet we send.
	return struct.pack(">I", len(serialized)) + serialized

def protobuf_to_json(struct_map, data):
	"""
	Extremely simplified de-serializer from ProtoBuf -> JSON.
	It doesn't support dict lengths larger than 65535 bytes in any given string field.
	"""
	key_map = list(struct_map.keys())
	val_map = list(struct_map.values())
	index = 0
	data_index = 0

	INT = 0
	DOUBLE = 1
	STRING = 2
	# deprecated:
	# 3 = start group
	# 4 = end group
	FLOAT = 5

	result = OrderedDict()

	while data_index < len(data):
		identifier = data[data_index]
		data_index += 1
		MSB = identifier & 0b10000000
		field_number = (identifier & 127) >> 3 # Remove MSB and remove wire_type
		wire_type = identifier & 7

		if wire_type == INT:
			val = struct.unpack('B', data[data_index:data_index+1])[0]

			data_index += 1
			result[key_map[field_number-1]] = val_map[field_number-1](val)
		elif wire_type == STRING:
			length = struct.unpack('B', data[data_index:data_index+1])[0]
			if length & 0b10000000: # MSB set
				length = data[data_index:data_index+2]
				length = bin(length[1] & 127)[2:].zfill(7) + bin(length[0] & 127)[2:].zfill(7)   # (MSB removal) -> Flip -> Combine: https://developers.google.com/protocol-buffers/docs/encoding#varints
				length = int(length, 2)
				data_index += 1
			elif length & 0b10000000: # Check the second byte
				length = struct.unpack('>I', data[data_index:data_index+4])[0]
				data_index += 3
				raise ValueError('Not yet implemented')
			elif length & 0b10000000: # And so on, make this recursive.
				length = ...
				raise ValueError('Not yet implemented')

			string = data[data_index+1:data_index+1+length]

			data_index += 1 + length
			result[key_map[field_number-1]] = val_map[field_number-1](string.decode('UTF-8'))
		else:
			break

	return dict(result)

def _format_session_params(_req_count, param_dict):
	req_count = REQ_PREFIX.format(req_id=_req_count)
	return {req_count + k if k.startswith("_") else k: v for k, v in param_dict.items()}

ss.send(json_to_protobuf({
	'protocol_version' : 0,
	'source_id' : 'sender-0',
	'destination_id' : SESSION,
	'namespace' : CONNECT_URL,
	'payload_type' : 0,
	'payload_utf8' : json.dumps({"type": "CONNECT"}, ensure_ascii=False)
}))
ss.send(json_to_protobuf({
	'protocol_version' : 0,
	'source_id' : 'sender-0',
	'destination_id' : SESSION,
	'namespace' : RECEIVER_URL,
	'payload_type' : 0,
	'payload_utf8' : json.dumps({"type": "GET_STATUS"}, ensure_ascii=False)
}))
ss.send(json_to_protobuf({
	'protocol_version' : 0,
	'source_id' : 'sender-0',
	'destination_id' : SESSION,
	'namespace' : RECEIVER_URL,
	'payload_type' : 0,
	'payload_utf8' : json.dumps({"type": "LAUNCH", "requestId": 1, "appId": LAUNCH_APP}, ensure_ascii=False)
}))

while 1:
	message_length = struct.unpack('>I', ss.recv(4))[0]
	raw_message = ss.recv(message_length)

	message = protobuf_to_json({
		'protocol_version' : int,
		'source_id' : str,
		'destination_id' : str,
		'namespace' : str,
		'payload_type' : int,
		'payload_utf8' : str
	}, raw_message)
	
	data = json.loads(message['payload_utf8'])

	if 'type' in data and data['type'].lower() == 'ping':
		ss.send(json_to_protobuf({
			'protocol_version' : 0,
			'source_id' : 'sender-0',
			'destination_id' : SESSION,
			'namespace' : HEARTBEAT_URL,
			'payload_type' : 0,
			'payload_utf8' : json.dumps({"type": "PONG"}, ensure_ascii=False)
		}))
	elif 'type' in data and data['type'].lower() == 'receiver_status':
		if 'status' in data and 'applications' in data['status'] and data['status']['applications'][0]['appId'] == APP_YOUTUBE:
			## YouTube has launched.
			## We need to connect to that newly launched session.
			print('YouTube app has launched on the chromecast.')
			SESSION = data['status']['applications'][0]['sessionId']

			ss.send(json_to_protobuf({
				'protocol_version' : 0,
				'source_id' : 'sender-0',
				'destination_id' : SESSION,
				'namespace' : CONNECT_URL,
				'payload_type' : 0,
				'payload_utf8' : json.dumps({"type": "CONNECT"}, ensure_ascii=False)
			}))
			ss.send(json_to_protobuf({
				'protocol_version' : 0,
				'source_id' : 'sender-0',
				'destination_id' : SESSION,
				'namespace' : YOUTUBE_URL,
				'payload_type' : 0,
				'payload_utf8' : json.dumps({'type': 'getMdxSessionStatus'}, ensure_ascii=False)
			}))
		elif 'status' in data and 'applications' in data['status'] and data['status']['applications'][0]['appId'] == APP_MEDIA_RECIEVER:
			print('Generic media player app has launched on the chromecast.')
			SESSION = data['status']['applications'][0]['sessionId']

			# Connect to the new Generic media player sessionId.
			ss.send(json_to_protobuf({
				'protocol_version' : 0,
				'source_id' : 'sender-0',
				'destination_id' : SESSION,
				'namespace' : CONNECT_URL,
				'payload_type' : 0,
				'payload_utf8' : json.dumps({"type": "CONNECT"}, ensure_ascii=False)
			}))

	# Generic media player section:
	elif 'type' in data and data['type'] == 'MEDIA_STATUS' and data['status'] == []:
		# If we recieve a MEDIA_STATUS that is empty,
		# It means it's ready to play something.

		print(f'Starting generic video: {VIDEO_ID}')
		# https://developers.google.com/cast/docs/reference/messages#MediaData
		video_payload = {
			'type' : 'LOAD',
			'media' : {
				"contentId": VIDEO_ID,
				"streamType": 'BUFFERED',
				"contentType": 'video/mp4',
				#"metadata": {
				#	"title" : "something",
				#	"images" : [{"url": "https://"}]
				#}
			},
			# "currentTime" : 0, # Defauklts to 0
			# "autoplay" : True, # Default is True
			"customData" : {},
			"requestId" : 3
		}

		ss.send(json_to_protobuf({
			'protocol_version' : 0,
			'source_id' : 'sender-0',
			'destination_id' : SESSION,
			'namespace' : GENERIC_MEDIA_URL,
			'payload_type' : 0,
			'payload_utf8' : json.dumps(video_payload, ensure_ascii=False)
		}))

	# YouTube specific query/response section:
	elif 'type' in data and data['type'].lower() == 'mdxsessionstatus':
		## Got the lounge_id (screen_id) from the current YouTube session on the chromecast.
		## We need this to HTTP-bind to the lounge and insert video_id's into the lounge.
		SCREEN_ID = data['data']['screenId']
		# DEVICE_ID = data['data']['deviceId']

		# -- HTTP stuff --
		# * Access Token *
		# Execute a HTTPS post to to get a Access Token for the lounge ID started by the chromecast.
		http_post_payload = urllib.parse.urlencode({"screen_ids": SCREEN_ID}).encode()
		http_request_obj =  urllib.request.Request("https://www.youtube.com/api/lounge/pairing/get_lounge_token_batch", data=http_post_payload)
		http_response = urllib.request.urlopen(http_request_obj)
		lounge_json_data = json.loads(http_response.read().decode('UTF-8'))

		# Store the Access Token
		LOUNGE_TOKEN = lounge_json_data['screens'][0]['loungeToken']

		# * Bind to lounge *
		# Execute a HTTP post to bind a Cookie session to the lounge using the access token.
		http_url_query = urllib.parse.urlencode({'RID': 0, 'VER': 8, 'CVER': 1})
		http_post_headers = {'X-YouTube-LoungeId-Token' : LOUNGE_TOKEN}
		bind_url = "https://www.youtube.com/api/lounge/bc/bind?%s" % http_url_query
		http_post_payload = urllib.parse.urlencode(YOUTUBE_API_BIND_DATA).encode()
		http_request_obj =  urllib.request.Request(bind_url, data=http_post_payload, headers=http_post_headers)
		http_response = urllib.request.urlopen(http_request_obj)
		
		# Store the session-cookie:
		bind_raw_data = http_response.read().decode('UTF-8')
		for key, val in http_response.getheaders():
			if key.lower() == 'set-cookie':
				COOKIE = val.split(';',1)[0].strip()

		# Find the SID and gsessionid - located in a weirdly formatted HTTP response (chunked transfer encoding)
		sid = re.search(SID_REGEX, bind_raw_data)
		gsessionid = re.search(GSESSION_ID_REGEX, bind_raw_data)
		
		SID = sid.group(1)
		GSESSION_ID = gsessionid.group(1)

		# Once we've got a access token, are bound to the lounge - we can start a video.
		print(f'Starting YouTube video {VIDEO_ID}')

		request_data = {"_listId": "",
						"__sc": "setPlaylist",
						"_currentTime": "0",
						"_currentIndex": -1,
						"_audioOnly": "false",
						"_videoId": VIDEO_ID,
						"count": 1}
		url_params = {"SID": SID, "gsessionid": GSESSION_ID,
						"RID": 1, "VER": 8, "CVER": 1}
		request_data = _format_session_params(0, request_data)

		http_url_query = urllib.parse.urlencode(url_params)
		http_post_headers = {'X-YouTube-LoungeId-Token' : LOUNGE_TOKEN, 'Cookie' : COOKIE}
		bind_url = "https://www.youtube.com/api/lounge/bc/bind?%s" % http_url_query
		http_post_payload = urllib.parse.urlencode(request_data).encode()
		http_request_obj =  urllib.request.Request(bind_url, data=http_post_payload, headers=http_post_headers)
		http_response = urllib.request.urlopen(http_request_obj)

		video_play_raw_data = http_response.read().decode('UTF-8')
		
	time.sleep(0.5)