# chromecast
As vanilla as it gets, cast a youtube video to a chromecast

# Requirements

 * [Google](https://pypi.org/project/google/)
 * [Google ProtoBuf](https://developers.google.com/protocol-buffers/docs/pythontutorial) *(optional)* if you want to compile the `.proto`.<br>
   The easiest way to install this would probably be `pip3 install protobuf`. But on Windows this will cause issues.

# Usage

    python chromecast.py <video id>

For instance:

    python chromecast.py ZTidn2dBYbY

# Note

Two things, one, just use [pychromecast](https://github.com/home-assistant-libs/pychromecast) or [casttube](https://github.com/ur1katz/casttube). They're more fully fledged.<br>
Second thing is that the `.proto` file is just something that google created in order to create the `.py` file. Which in short is just a meta-class constructor which handles your "protocol" (struct) definition.<br>
Which in turn is just a overengineered serializer for something that starts out as JSON data.

tl;dr: `.proto` is just a `JSON` serializer.

![flowchart](flowchart.png)
