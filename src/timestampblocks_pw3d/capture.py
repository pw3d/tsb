#!/usr/bin/python3

#.timestampblocks.methods
# - git
# - ethereum
# - bitcoin
# - iota
#.timestampblocks.ignore
# - .timestampblocks.*

#TODO:
# contract and logic for evm publishing (add publishing arguments to constructor in case we need to deploy first)
# rethink encoding of message, possibly different for evm
# -> ha, for now we simply send transactions with block_root as to_address

import configparser
import argparse
import hashblock
import os
import hashlib
import pathspec
from pathlib import Path
import time
from datetime import datetime
from dotenv import dotenv_values
from web3 import Web3

from iota_client import IotaClient

_possible_publish = ("git", "iota", "shell", "evm")
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

_dotenv = dotenv_values(".env")

_config = {
    "default": {
        "publish": "git shell",
        "hashing": "sha384",
    },
    "iota": {
        "protocol": "iota",
        "node": "https://iota-node.tanglebay.com",
    },
    "evm": {
        "protocol": "evm",
        "node": "https://goerli.infura.io/v3/",
        "api-key": "INFURA_SECRET",
        "private-key": "EVM_SECRET",
    }
}

def main():
    settings = configparser.ConfigParser()
    settings.read(_config_file)
    if not settings.has_section("default"):
        settings["default"] = _config["default"]
        with open(_config_file, "w") as configfile:
            settings.write(configfile)
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
    parser.add_argument('-d', '--dummy', action="store_true",
                        help="only print on shell and do not push or write block updates otherwise")
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
        assert not args.dummy, "settings update not possible as dummy version yet"
        settings = query_configuration(settings)
        with open(_config_file, "w") as configfile:
            settings.write(configfile)
    elif command == "update":
        hash_set, last_root, last_proper_root = evaluate_previous_logs(settings)
        new_hashes = get_new_hashes(hash_set, settings["default"]["hashing"])
        if len(new_hashes) > 0 or _publish_even_if_no_changes:
            new_block = build_block(new_hashes, last_root, last_proper_root, settings["default"]["hashing"])
            if not args.dummy:
                with open(_log_file, "a") as f:
                    if (last_root != last_proper_root):
                        f.write("#hashing "+settings["default"]["hashing"]+"\n")
                    f.write(new_block["data"]+"\n")
                    f.write("#root " + new_block["root"]+"\n")
            else:
                print("-dummy-", "not actually writing log file")
            publishers = settings["default"]["publish"].split()
            for channel in publishers:
                publish(channel, new_block, args.assume_yes, args.dummy)
        else:
            print("no updates detected")

def publish(channel, block, assume_yes, dummy):
    response = None
    if channel == "shell":
        response = publish_shell(block, assume_yes, dummy)
    elif channel == "git":
        response = publish_git(block, assume_yes, dummy)
    elif channel == "iota":
        response = publish_iota(block, assume_yes, dummy)
    else:
        settings = configparser.ConfigParser()
        settings.read(_config_file)
        if settings.has_section(channel):
            if settings[channel]["protocol"] == "evm":
                response = publish_evm(block, assume_yes, dummy, channel=channel)
            else:
                print("Custom channel not implemented yet!", channel, block, assume_yes, dummy)
        else:
            print("Channel not implemented yet!", channel, block, assume_yes, dummy)
    if response != None:
        # TODO log the response (likely a transaction id)
        print("response:", response)
        pass

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

def publish_evm(block, assume_yes, dummy=False, channel="evm"):
    settings = configparser.ConfigParser()
    settings.read(_config_file)
    if not settings.has_section(channel):
        settings = _config
    web3 = Web3(Web3.HTTPProvider(settings[channel]["node"] + _dotenv[settings[channel]["api-key"]]))
    account = web3.eth.account.from_key(_dotenv[settings[channel]["private-key"]])
    nonce = web3.eth.getTransactionCount(account.address)
    recipient = web3.toChecksumAddress("0x" + block["root"][:40]) #trick to publish block_root via to_address
    tx = {
        "nonce": nonce,
        "to": recipient,
        "value": 0,
        "gas": 20000000,
        "gasPrice": web3.eth.gasPrice
    }
    signed_tx = account.sign_transaction(tx)
#    signed_tx = web3.eth.account.sign.transaction(tx, _dotenv[settings[channel]["private-key"]])
    if dummy:
        print("-dummy-", "not publishing on", channel, signed_tx)
    else:
        tx_hash = web3.eth.sendRawTransaction(signed_tx.rawTransaction)
        return tx_hash

def publish_iota(block, assume_yes, dummy=False):
    settings = configparser.ConfigParser()
    settings.read(_config_file)
    node_uri = _config["iota"]["node"]
    if settings.has_section("iota"):
        node_uri = settings["iota"]["node"]
    client = IotaClient({'nodes': [node_uri]})
    options = {
        "tag": "0x" + "timehashblock".encode("utf-8").hex(),
        "data": "0x" + block["root"],
    }
    if dummy:
        print("-dummy-", "not publishing on iota", options)
    else:
        response = client.build_and_post_block(None, options)
        return response

def publish_git(block, assume_yes, dummy=False):
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
            if dummy:
                print("-dummy-", "not running `git add --force", _log_fle + "`")
            else:
                os.system("git add --force " + _log_file)
    print("Git submission:")
    if not assume_yes:
        os.system("git add -n .")
        print("Proceed? (Yn)")
        if input() == "n":
            print("Aborting...")
            return
    if dummy:
        print("-dummy-", "not running `git add .`")
    else:
        os.system("git add .")
    if not assume_yes:
        os.system("git status")
        print("Proceed? (Yn)")
        if input() == "n":
            print("Aborting...")
            return
    if dummy:
        print("-dummy-", "not running `git commit -a -m 'timestampblocks update for root " + block["root"] + "'`")
        print("-dummy-", "not running `git push`")
    else:
        os.system("git commit -a -m 'timestampblocks update for root " + block["root"] + "'")
        os.system("git push")

def publish_shell(block, assume_yes, dummy=False):
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
    channels = set(settings["default"]["publish"].split())
    if "iota" in channels:
        if not settings.has_section("iota"):
            settings["iota"] = _config["iota"]
        print("------- iota")
        settings["iota"] = query_protocol("iota", settings["iota"])
    if "evm" in channels:
        if not settings.has_section("evm"):
            settings["evm"] = _config["evm"]
        print("------- evm")
        settings["evm"] = query_protocol("evm", settings["evm"])
    for channel in channels:
        if not channel in _possible_publish:
            if not settings.has_section(channel):
                protocol = "evm"
            else:
                protocol = settings[channel].get("protocol", "evm")
            print("-------", channel)
            print("protocol (" + protocol +")")
            inp = input()
            new_protocol = protocol
            if len(inp) > 0:
                new_protocol = inp
            if not settings.has_section(channel) or protocol != new_protocol:
                settings[channel] = _config[new_protocol]
            settings[channel] = query_protocol(channel, settings[channel])
    print("-----------------------")
    print("Default hash algorithm:")
    print(" - available: " + str(hashlib.algorithms_available))
    print(" - currently: '" + settings["default"]["hashing"]+"'")
    inp = input()
    if len(inp) > 0:
        settings["default"]["hashing"] = inp
    return settings

def query_protocol(channel, default_dic, skip_list = ["protocol"]):
    dd = dict(default_dic).copy()
    for key in dd:
        if not key in skip_list:
            print(key, "(" + dd[key] + ")")
            inp = input()
            if len(inp) > 0:
                dd[key] = inp
            keysplit = key.split('-')
            if len(keysplit) > 1 and keysplit[-1] == "key":
                keyname = key.upper()
                print(" - store secret as (" + keyname + ") to \".env\" file (no input here means manual editing required)")
                inp = input()
                if len(inp) > 0:
                    with open(".env", "a") as envfile:
                        envfile.write(dd[key]+"=\""+inp+"\"\n")
                    global _dotenv
                    _dotenv = dotenv_values(".env")
    return dd

if __name__ == "__main__":
    main()
