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