#!/bin/bash

replay_file=envyus-vs-natus-vincere-map2-cbble.dem
#replay_file=some_image.jpg
#replay_file=sometext.txt
sha1sum=$(sha1sum $replay_file | cut -d " " -f 1)
echo $sha1sum

tempurl=$(curl -s -F "game=sc2" -F "replay_sha1sum=${sha1sum}" '0.0.0.0:8081/upload?' | grep http | cut -d " " -f 12 | cut -d "<" -f 1)
echo "tempurl:"
echo $tempurl

#curl -i -XPUT -H "Content-Type: application/octet-stream" --upload-file  ${replay_file} $tempurl
