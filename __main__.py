"""
Copyright (c) 2012, Kevin Han
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

    Redistributions of source code must retain the above copyright notice, this
    list of conditions and the following disclaimer.

    Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions and the following disclaimer in the documentation
    and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import os
import string
import itertools
import re
import glob
import argparse
from collections import namedtuple

from parsing import utils as putils

# match C comments that signal a possible function afterwards
COMMENT_RE = re.compile(r'^\s*(/\*.+?\*/)\s*$', flags=re.M | re.DOTALL)

class FuncData:
    def __init__(self, name, header, endI, cmt=None):
        self.name = name
        self.header = header
        self.endI = endI
        self.cmt = cmt
    def __repr__(self):
        s = '(' + ', '.join((repr(self.name), repr(self.header), repr(self.endI)))
        if self.cmt is not None:
            s += ', ' + repr(self.cmt)
        s += ')'
        return s

def printV(*_args):
    if args.verbose:
        print ' '.join(str(arg) for arg in _args)

def isWS(c):
    return c in string.whitespace

def getFuncData(code, i, fromDefn=False):
    """
    Return function declaration data starting from i, or None if i does not mark
    the start of a function declaration.

    If fromDefn is True, i must mark the start of a definition instead, and the
    return value is a FuncData object:
    
    (name=<function name>, header=<function header>, endI=<index after closing brace>)

    If False, return value looks like this:

    (name=<function name>, header=<function header>, endI=<index after semicolon>)

    >>> getFuncData('int main();', 0)
    ('main', 'int main()', 10)
    >>> getFuncData('int main() {return 0;}', 0, fromDefn=True)
    ('main', 'int main()', 22)
    >>> print getFuncData('int main();', 0, fromDefn=True)
    None
    """
    try:
        parenStartI, parenEndI = putils.findMatching(code, '(', ')', startI=i)
    except ValueError:
        return None

    header = code[i:parenEndI].strip()

    if not header[0].isalpha():
        return None

    # braces not allowed in function declarations; this distinguishes from
    # struct, etc.
    if '{' in header or '}' in header:
        return None

    # check for control flow statements (if, while, etc)
    if len(code[i:parenStartI].split()) <= 1:
        return None

    name = code[i:parenStartI].split()[-1].lstrip('*')

    if not fromDefn:
        return FuncData(
                name=name,
                header=header,
                endI=code.find(';', parenEndI) + 1
                )

    # check if next char after parentheses is '{'
    if itertools.dropwhile(isWS, code[parenEndI:]).next() != '{':
        return None

    return FuncData(
            name=name,
            header=header,
            endI=putils.findMatching(code, '{', '}', startI=parenEndI)[1]
            )

def makeDecl(fData):
    """Create declaration from fData."""
    if fData.cmt:
        return fData.cmt + '\n' + fData.header + ';'
    else:
        return fData.header + ';'

parser = argparse.ArgumentParser(
        description='Given C source file(s) as input, creates/updates header files with relevant function declarations.'
        )

parser.add_argument(
        'files',
        metavar='PATTERN',
        nargs='+',
        help='source files to process'
        )

parser.add_argument(
        '-q',
        '--quiet',
        dest='verbose',
        default=True,
        action='store_false',
        help="don't print what it's doing"
        )

args = parser.parse_args()

for path in itertools.chain(*(glob.glob(pat) for pat in args.files)):
    newPath = path.rsplit('.', 1)[0] + '.h'
    code = open(path).read()
    printV('opened', path)

    # extract function definitions with documentation
    defnData = []
    startI = 0
    while True:
        match = COMMENT_RE.search(code, startI)
        if not match:
            break
        cmt = match.group(1)
        fData = getFuncData(code, match.end(), fromDefn=True)
        if fData is None:
            startI = match.end()
        else:
            fData.cmt = cmt
            defnData.append(fData)
            startI = fData.endI

    # remove local (private) functions, signified by starting with '_' 
    defnData = [d for d in defnData \
            if not d.name.startswith('_') and not d.header.startswith('static')]

    # mapping of name to FuncData
    nameToDefn = dict((data.name, data) for data in defnData)

    printV('read %d function definitions' % len(defnData))

##    from pprint import pprint
##    pprint(defnData)
##    print len(defnData)

    changed = False

    if os.path.isfile(newPath):
        headCode = open(newPath, 'r').read()
        printV('opened', newPath)
    else:
        changed = True
        headCode = '#pragma once\n'

    startI = 0
    while True:
        match = COMMENT_RE.search(headCode, startI)
        if not match:
            break
        cmt, decl = match.group(1), getFuncData(headCode, match.end())
        if decl is None:
            startI = match.end()
            continue

        if decl.name in nameToDefn:
            printV('found', decl.name)
            decl.cmt = cmt
            defn = nameToDefn[decl.name]
            if decl.cmt != defn.cmt or decl.header != defn.header:
                changed = True
                printV('updating', decl.name)
                headCode = '%s%s%s' \
                        % (headCode[:match.start(1)], makeDecl(defn), headCode[decl.endI:])
            del nameToDefn[decl.name]
        else:
            printV('%s not found in %s, deleting' % (decl.name, path))
            headCode = '%s%s' \
                    % (headCode[:match.start(1)], headCode[decl.endI:])

        startI = decl.endI

    for defn in nameToDefn.values():
        changed = True
        printV('adding', defn.name)
        headCode += '\n' + makeDecl(defn) + '\n'

    if changed:
        open(newPath, 'w').write(headCode)
        printV('wrote', newPath)
    else:
        printV('nothing changed')
