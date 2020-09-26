# chromecast
As vanilla as it gets, cast a youtube video to a chromecast

# Requirements

There are one requirement, and that is [Google ProtoBuf](https://developers.google.com/protocol-buffers/docs/pythontutorial) library.<br>
The easiest way to install this would probably be `pip3 install protobuf`.

You can compile the `chromecast.proto` yourself. But this will be removed for a vanilla constructor later to remove this dependency. We don't use all the features anyway.

# Usage

    python chromecast.py <video id>

For instance:

    python chromecast.py ZTidn2dBYbY

# Note

Two things, one, just use [pychromecast](https://github.com/home-assistant-libs/pychromecast) or [casttube](https://github.com/ur1katz/casttube). They're more fully fledged.<br>
Second thing is that the `.proto` file is just something that google created in order to create the `.py` file. Which in short is just a meta-class constructor which handles your "protocol" (struct) definition.<br>
Which in turn is just a overengineered serializer for something that starts out as JSON data.

tl;dr: `.proto` is just a `JSON` serializer.