#!/usr/bin/python3

#.timestampblocks.methods
# - git
# - ethereum
# - bitcoin
# - iota
#.timestampblocks.ignore
# - .timestampblocks.*

import configparser
import argparse
import hashblock
import os
import iota_client
import hashlib
import pathspec
from pathlib import Path
import time
from datetime import datetime

_possible_publish = ("git", "iota", "polygon", "shell")
_available_commands = ("update", "query-settings")
_tsb_dir = ".timestampblocks/"
if not os.path.exists(_tsb_dir):
    os.makedirs(_tsb_dir)
_config_file = _tsb_dir + "config"
#_tree_file = _tsb_dir + "tree"
#_last_hash_set = _tsb_dir + "hash_set"
_log_file = "timestampblocks.log"
_log_version=1
_blocksize = 65536
_publish_even_if_no_changes = False

_config = {
    "default": {
        "publish": "git shell",
        "hashing": "sha384",
    },
}

def main():
    settings = configparser.ConfigParser()
    settings.read(_config_file)
    write_config = False
    if not settings.has_section("default"):
        settings["default"] = _config["default"]
        write_config = True
    parser = argparse.ArgumentParser()
    parser.add_argument('command', nargs=1,
                        help="options are "+str(_available_commands))
    parser.add_argument('-y', '--assume-yes', action="store_true",
                        help="the 'no input required' option")
    parser.add_argument('-s', '--hashing', nargs=1, default=[settings["default"]["hashing"]],
                        metavar="algorithm",
                        help="options are "+str(hashlib.algorithms_available)+",\n"+
                        "(setting is '" + settings["default"]["hashing"]+"')")
    parser.add_argument('-p', '--publish', nargs="+", default=settings["default"]["publish"].split(),
                        metavar="channel",
                        help="options are "+str(_possible_publish)+",\n"+
                        "(setting is " + str(settings["default"]["publish"].split())+")")
#    parser.add_argument('-m', '--message', nargs=1, metavar="text",
#                        help="optional message where publishing channel allows a message")
#    parser.add_argument('-', '--parameters', nargs="+",
#                        metavar="path",
#                        help="files to be selected")
#    parser.add_argument('params', nargs="*",
#                        metavar="path [path ...]",
#                        help="files to be selected")
    args = parser.parse_args()

    if args.hashing != None:
        settings["default"]["hashing"] = args.hashing[0]
    if len(args.publish) > 0:
        settings["default"]["publish"] = ' '.join(args.publish)

#    params = args.params
#    if args.parameters != None:
#        assert len(args.params)==0, "either use parameters or params, it's confusing if you use both"
#        params = args.parameters

    command = args.command[0]
    if command == "query-settings":
#        assert len(params) == 0, "no parameters allowed for this command!"
        write_config = True
        settings = query_configuration(settings)
    elif command == "update":
        hash_set, last_root, last_proper_root = evaluate_previous_logs(settings)
        new_hashes = get_new_hashes(hash_set, settings["default"]["hashing"])
        if len(new_hashes) > 0 or _publish_even_if_no_changes:
            new_block = build_block(new_hashes, last_root, last_proper_root, settings["default"]["hashing"])
            with open(_log_file, "a") as f:
                if (last_root != last_proper_root):
                    f.write("#hashing "+settings["default"]["hashing"]+"\n")
                f.write(new_block["data"]+"\n")
                f.write("#root " + new_block["root"]+"\n")
            publishers = settings["default"]["publish"].split()
            for channel in publishers:
                publish(channel, new_block, args.assume_yes)
        else:
            print("no updates detected")

    if write_config:
        with open(_config_file, "w") as configfile:
            settings.write(configfile)

def publish(channel, block, assume_yes):
    if channel == "shell":
        publish_shell(block, assume_yes)
    elif channel == "git":
        publish_git(block, assume_yes)
    else:
        print("Not implemented yet!", channel, block, assume_yes)

#    elif publishing_method == 'iota':
#        pass
#    elif publishing_method == 'polygon':
#        pass
#    elif publishing_method == 'arbitrum':
#        pass
#    elif publishing_method == 'bitcoin':
#        pass
#    elif publishing_method == 'ethereum':
#        pass

def publish_iota(block, assume_yes):
    pass

def publish_git(block, assume_yes):
    if len(str(os.popen("git check-ignore .env").read())) == 0:
        print(".env file is not excluded from git!")
        print("Add .env to .gitignore? (Yn)")
        inp = "Y"
        if assume_yes:
            print(inp)
        else:
            inp = input()
        if inp != "n":
            with open(".gitignore", "a") as file:
                file.write(".env")
    if len(str(os.popen("git ls-files ./" + _log_file).read())) == 0:
        print(_log_file, "is ignored by git")
        print("Run 'git add --force", _log_file+"'? (Yn)")
        inp = "Y"
        if assume_yes:
            print(inp)
        else:
            inp = input()
        if inp != "n":
            os.system("git add --force " + _log_file)
    print("Git submission:")
    if not assume_yes:
        os.system("git add -n .")
        print("Proceed? (Yn)")
        if input() == "n":
            print("Aborting...")
            return
    os.system("git add .")
    if not assume_yes:
        os.system("git status")
        print("Proceed? (Yn)")
        if input() == "n":
            print("Aborting...")
            return
    os.system("git commit -a -m 'timestampblocks update for root " + block["root"] + "'")
    os.system("git push")

def publish_shell(block, assume_yes):
    print("New block with root '"+ block["root"]+"', and data:")
    print(block["data"])
    print("Used hashing algorithm:", block["hashing"])
    print("Timestamp:", block["timestamp"], "--", datetime.fromtimestamp(block["timestamp"]))

def build_block(new_hashes, last_root, last_proper_root, hashing):
    timestamp = int(time.time())
    line_builder = [str(timestamp)]
    if len(last_proper_root) > 0 and last_root != last_proper_root:
        line_builder.append(last_proper_root)
    if len(last_root) > 0:
        line_builder.append(last_root)
    line_builder.extend(new_hashes)
    line = " ".join(line_builder)
    algo = hashlib.new(hashing)
    algo.update(line.encode("utf-8"))
    block = {
        "root": algo.hexdigest(),
        "data": line,
        "timestamp": timestamp,
        "hashed_files": new_hashes,
        "hashing": hashing
    }
    return block

def get_new_hashes(hash_set, hashing):
    files = Path().glob("**/*")
    lines = []
    if Path(".gitignore").exists():
        lines = Path(".gitignore").read_text().splitlines()
    lines = lines + [_log_file]
    spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
    files = [
        file for file in files if not spec.match_file(str(file))
    ]
    new_hashes = set()
    for file in files:
        if file.is_dir():
            continue
        filename = str(file)
        algo = hashlib.new(hashing)
        try:
            with open(file, 'rb') as f:
                fb = f.read(_blocksize)
                while len(fb) > 0:
                    algo.update(fb)
                    fb = f.read(_blocksize)
        except:
            pass
        hash_value = algo.hexdigest()
        if hash_value not in hash_set:
            new_hashes.add(hash_value)
    return list(new_hashes)

def evaluate_previous_logs(settings):
    log_version=0
    hash_set = set()
    hashing = ""
    last_root = ""
    last_hashing_root = ""
    previous_line = ""
    if Path(_log_file).exists():
        lines = Path(_log_file).read_text().splitlines()
        for line in lines:
            if line[0] == "#":
                if line.startswith("#timehashblock v"):
                    log_version=int(line[16:])
                elif line.startswith("#hashing "):
                    hashing = line[9:]
                elif line.startswith("#root "):
                    last_root = line[6:]
                    if hashing == settings["default"]["hashing"]:
                        last_hashing_root = last_root
                    algo = hashlib.new(hashing)
                    algo.update(previous_line.encode("utf-8"))
                    assert last_root == algo.hexdigest()
            else:
                previous_line = line
                if hashing == settings["default"]["hashing"]:
                    hash_set.update(line.split())
    if log_version != _log_version:
        assert log_version < _log_version, "existing log is more advanced than this program"
        with open(_log_file, 'a') as file:
            file.write("#timehashblock v"+str(_log_version)+"\n")
    return hash_set, last_root, last_hashing_root

def query_configuration(settings):
    print("Adjusting Configuration")
    print("-----------------------")
    print("Default publish channels:")
    print(" - available: " + str(_possible_publish))
    print(" - currently: '" + settings["default"]["publish"]+"'")
    inp = input()
    if len(inp) > 0:
        settings["default"]["publish"] = inp
    print("-----------------------")
    print("Default hash algorithm:")
    print(" - available: " + str(hashlib.algorithms_available))
    print(" - currently: '" + settings["default"]["hasing"]+"'")
    inp = input()
    if len(inp) > 0:
        settings["default"]["hashing"] = inp
    return settings

if __name__ == "__main__":
    main()
