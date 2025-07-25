
from typing import Optional, BinaryIO
import os.path

# Spoiler levels:
# 0: can be posted anywhere, main branes, white void, funhouse, etc. (since you can go there at any time)
# 1: hard mode, hard mode ending, only allowed to be posted in >=spoilers-vs
# 2: dis, only allowed to be posted in >=super-ultra-mega-spoilers
# 3: devend, EX, only allowed in postgame or ae
#
# cif's floors don't get their own level because there is very little that is unique to cif's run that couldn't be seen beforehand
# the spoiler levels correspond to folders in the `floors` directory

BASE_PATH = os.path.abspath("floors")

def get_floor_image(name: str, spoilerlvl: int) -> Optional[BinaryIO]:
    name = normalise_room_name(name)  + ".png"

    # additional directory traversal protection
    if ".." in name:
        return None
    
    # look for the room in ascending order of spoiler level
    for currlvl in range(spoilerlvl+1):
        image_path = os.path.join(BASE_PATH, str(currlvl), name)

        if (os.path.exists(image_path) and os.path.commonprefix([image_path, BASE_PATH]) == BASE_PATH):
            # check the file exists and that directory traversal isn't going on (it wouldn't be great to let someone request the discord token as a key)
            return open(image_path, mode="br")
        
    return None # could not find the image in the relevant spoiler categories
    

def normalise_room_name(name: str) -> str:
    # special case: if the name is a set of numeric characters, assume normal path
    if name.isdigit():
        name = "B" + name.zfill(3) 

    # normalize the name string
    name = name.upper().strip()

    return name