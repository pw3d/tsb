#!/usr/bin/python3

#.timestampblocks.methods
# - git
# - ethereum
# - bitcoin
# - iota
#.timestampblocks.ignore
# - .timestampblocks.*

#only include files/folders with new hashes? this as an option?
#or have block sections old and new

import configparser
import argparse
import hashblock

_possible_methods = ("git", "iota", "polygon", "shell")
_configfile_name = ".timestampblocks"
_config_default = {
    "SETTINGS": {
        "ignorefile": ".gitignore",
        "methods": "git shell",
        "hashmethod": "sha384",
        "hashfile": "timestampblock.txt",
    },
}
_settings = None

def current_settings():
    global _settings
    if _settings == None:
        _settings = configparser.ConfigParser()
        _settings.read(_configfile_name)
    return _settings

def main():
    parser = argparse.ArgumentParser(
        "Timestamp Blocks",
        "Timestamping Organization Utility",
        "Be sure to stamp that into a block!")
    global _configfile_name
    parser.add_argument('-c', '--config', nargs=1)
    parser.add_argument('-i', '--ignorefile', nargs=1)
    parser.add_argument('-s', '--save-settings', action="store_true")
    parser.add_argument('-q', '--query-settings', action="store_true")
    parser.add_argument('-m', '--hashmethod', nargs=1)
    parser.add_argument('methods', nargs="*")
    args = parser.parse_args()
    if args.config != None:
        _configfile_name = args.config
    settings = current_settings()
    if args.hashmethod != None:
        settings["SETTINGS"]["hashmethod"] = args.hashmethod
    if not settings.has_section("SETTINGS"):
        settings["SETTINGS"] = {}
    if args.ignorefile != None:
        settings["SETTINGS"]["ignorefile"] = args.ignorefile
    if settings["SETTINGS"].get("ignorefile", None) == None:
        settings["SETTINGS"]["ignorefile"] = ".gitignore"
    if len(args.methods) > 0:
        settings["SETTINGS"]["methods"] = ' '.join(args.methods)
    if args.save_settings:
        with open(_configfile_name, "w") as configfile:
            settings.write(configfile)
    if args.query_settings:
        query_configuration()
    methods = settings["SETTINGS"].get("methods", "").split()
    block = hashblock.HashBlock(settings["SETTINGS"]["hashmethod"])
    block.scan(settings["SETTINGS"]["ignorefile"], settings["SETTINGS"]["hashfile"])
    for method in methods:
        block.apply(method)

def query_configuration():
    config = current_settings();
    print("Adjusting Configuration")
    for (section, dic) in _config_default.items():
        for (vkey, vvalue) in dic.items():
            if config.has_section(section):
                vvalue = config[section].get(vkey, vvalue);
            else:
                config[section] = {}
            print(" -", vkey, "*(" + vvalue + ")")
            inp = input()
            if len(inp) > 0:
                vvalue = inp
            config[section][vkey] = vvalue
    print("We have the following configuration")
    for section in config.sections():
        print(" ", section)
        for (vkey, vvalue) in config[section].items():
            print(" - ", vkey + ": ", vvalue)
    print("Save? (any key other than n or N will save to storage)");
    inp = input()
    if len(inp) == 0 or inp not in "nN":
        with open(_configfile_name, "w") as configfile:
            config.write(configfile)

if __name__ == "__main__":
    main()
