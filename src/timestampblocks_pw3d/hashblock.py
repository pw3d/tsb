import pathspec
from pathlib import Path
import time
import hashlib

class HashBlock:
    hash_method = None
    total_hash = None
    new_hash = None
    new_lines = None #dict with key=path, value=(file_hash, timestamp)
    old_hash = None
    old_lines = None #dict with key=path, value=(file_hash, timestamp)
    blocksize = 65536
    hashfile = None

    def __init__(self, hash_method):
        self.hash_method = hash_method
        self.new_lines = {}
        self.old_lines = {}

    def scan(self, ignorefile, hashfile):
        # currently:
        # id via path, sorting as old or new
        # merkle tree
        # root
        #   new
        #     ... files
        #   old
        #     ... files
        #
        # might be better:
        # sorting via last change date
        # id via hash
        # root
        #   entry with time
        #     timestamp
        #     ... filehashes
        #   ... other entries
        #
        # could mean timestampblock file structure:
        # roothash timestamp lastroothash hash1 hash2 hash3 ...
        self.hashfile = hashfile
        new_timestamp = str(int(time.time()))
        files = Path().glob('**/*')
        if Path(ignorefile).exists():
            lines = Path(ignorefile).read_text().splitlines()
            spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
            files = [
                file for file in files if not spec.match_file(str(file))
            ]
        file_names = {str(f) for f in files}
        if Path(hashfile).exists():
            # hashfile format:
            # | hash_method
            # | root: `root_hash = hash(new_hash, old_hash)`
            # | new: `new_hash = hash(nfilehash1, nfilehash2, ...)`
            # | old: `old_hash = hash(ofilehash1, ofilehash2, ...)`
            # | - + - newlines - + -
            # | nfilepath1 nfilehash1 nfiletimestamp1
            # | nfilepath2 nfilehash2 nfiletimestamp2
            # | nfilepath3 nfilehash3 nfiletimestamp3
            # more lines
            # | - + - oldlines - + -
            # | ofilepath1 ofilehash1 ofiletimestamp1
            # | ofilepath2 ofilehash2 ofiletimestamp2
            # | ofilepath3 ofilehash3 ofiletimestamp3
            # more lines
            lines = Path(hashfile).read_text().splitlines()
            if lines[0].lower() == self.hash_method.lower():
                #only do hash comparison if using the same hash_method again
                for line in lines[1:]:
                    try:
                        (key, value, timestamp) = line.split()
                        if key in self.old_lines:
                            raise Exception("duplicate entry: "+key)
                        if key in file_names:
                            self.old_lines[key] = (value, timestamp)
                    except:
                        #not a hashline
                        pass
        for file in files:
            if file.is_dir():
                continue
            file = str(file)
            if file == hashfile:
                continue
            file_hash = hashlib.new(self.hash_method)
            try:
                with open(file, 'rb') as f:
                    fb = f.read(self.blocksize)
                    while len(fb) > 0:
                        file_hash.update(fb)
                        fb = f.read(self.blocksize)
            except:
                #non-files
                pass
            hash_value = file_hash.hexdigest()
            if file in self.old_lines:
                (old_value, old_timestamp) = self.old_lines[file]
                if hash_value == old_value:
                    # should not be part of new lines
                    continue
                else:
                    del self.old_lines[file]
            self.new_lines[file] = (hash_value, new_timestamp)
        new_hash_values = [self.new_lines[key][0] for key in self.new_lines]
        new_hasher = hashlib.new(self.hash_method)
        new_hasher.update(
            '\n'.join(new_hash_values).encode("utf-8")
        )
        self.new_hash = new_hasher.hexdigest()
        old_hash_values = [self.old_lines[key][0] for key in self.old_lines]
        old_hasher = hashlib.new(self.hash_method)
        old_hasher.update(
            '\n'.join(old_hash_values).encode("utf-8")
        )
        self.old_hash = old_hasher.hexdigest()
        total_hasher = hashlib.new(self.hash_method)
        total_hasher.update(
            (self.new_hash+"\n"+self.old_hash).encode("utf-8")
        )
        self.total_hash = total_hasher.hexdigest()
        new_output_lines = [' '.join([vkey, self.new_lines[vkey][0], self.new_lines[vkey][1]]) for vkey in self.new_lines]
        old_output_lines = [' '.join([vkey, self.old_lines[vkey][0], self.old_lines[vkey][1]]) for vkey in self.old_lines]
        if len(self.new_lines) > 0:
            with open(hashfile, 'w') as file:
                file.write(self.hash_method+'\n')
                file.write('total: '+self.total_hash+'\n')
                file.write('new: '+self.new_hash+'\n')
                file.write('old: '+self.old_hash+'\n')
                file.write('- + - newlines - + -'+'\n')
                file.write('\n'.join(new_output_lines)+'\n')
                file.write('- + - oldlines - + -'+'\n')
                file.write('\n'.join(old_output_lines)+'\n')


